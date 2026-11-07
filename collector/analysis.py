"""Stockfish analysis of collected games.

Every position a game reached is evaluated once. Each move is then scored by how
much it changed the mover's winning chances, classified (best / good / inaccuracy /
mistake / blunder), labelled tactical or positional, and given two fingerprints:

* ``position_key`` - the exact position (pieces, side to move, castling, en passant),
  so the same opening position reached in different games groups together.
* ``structure_key`` - only the pawns and which wing each king is on, so similar
  middlegames with the same pawn structure group together.

The PGNs come from the Chess.com archive payloads the collector already caches in
``chess.http_cache``; nothing extra is fetched from Chess.com.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import logging
import math
import os
import shutil
import signal
import threading
import time
from dataclasses import dataclass, field
from importlib import resources

import chess
import chess.engine
import chess.pgn

log = logging.getLogger(__name__)

PIECE_VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
MATE_CP = 10_000          # centipawn stand-in for forced mate
EVAL_CLAMP = 2_000        # stored evals are clamped so mates don't swamp averages
# Drops in winning chances (percentage points) - the thresholds Lichess uses.
INACCURACY, MISTAKE, BLUNDER = 10.0, 20.0, 30.0
TACTICAL_PLIES = 6        # how far along a line to look for material changing hands
TACTICAL_MATERIAL = 2     # pawns of material that make a line "tactical"
ENDGAME_MATERIAL = 20     # combined non-pawn material (both sides) at or below = endgame
OPENING_MOVES = 10        # full moves counted as the opening


# --------------------------------------------------------------------------- scoring

def win_percent(cp: int) -> float:
    """Winning chances (0-100) for a centipawn eval, as used by Lichess."""
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


def classify(win_loss: float, played_best: bool) -> str:
    if played_best:
        return "best"
    if win_loss >= BLUNDER:
        return "blunder"
    if win_loss >= MISTAKE:
        return "mistake"
    if win_loss >= INACCURACY:
        return "inaccuracy"
    return "good"


def material_balance(board: chess.Board, colour: chess.Color) -> int:
    total = 0
    for piece_type, value in PIECE_VALUES.items():
        total += value * (len(board.pieces(piece_type, colour)) - len(board.pieces(piece_type, not colour)))
    return total


def balance_after_line(board: chess.Board, moves, colour: chess.Color, plies: int = TACTICAL_PLIES) -> int:
    """Material balance for ``colour`` after playing up to ``plies`` moves of a line.

    If the line is mid-exchange at the cut-off, keep following captures so a
    half-finished trade isn't mistaken for won or lost material.
    """
    board = board.copy(stack=False)
    for i, move in enumerate(moves):
        if move not in board.legal_moves:
            break
        is_capture = board.is_capture(move)
        if i >= plies and not is_capture:
            break
        board.push(move)
    return material_balance(board, colour)


def non_pawn_material(board: chess.Board) -> int:
    return sum(value * len(board.pieces(piece_type, colour))
               for piece_type, value in PIECE_VALUES.items() if piece_type != chess.PAWN
               for colour in chess.COLORS)


def phase(board: chess.Board) -> str:
    if non_pawn_material(board) <= ENDGAME_MATERIAL:
        return "endgame"
    if board.fullmove_number <= OPENING_MOVES:
        return "opening"
    return "middlegame"


# -------------------------------------------------------------------------- accuracy

ACCURACY_CEILING = 1_000  # Lichess caps evals at +-10 pawns before turning them into winning chances


def move_accuracy(win_before: float, win_after: float) -> float:
    """Lichess's per-move accuracy (0-100) from the mover's winning chances before and after."""
    if win_after >= win_before:
        return 100.0
    raw = 103.1668100711649 * math.exp(-0.04354415386753951 * (win_before - win_after)) - 3.166924740191411
    return max(0.0, min(100.0, raw + 1))  # +1: Lichess's allowance for imperfect analysis


def _std_dev(values: list[float]) -> float:
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


def game_accuracy(moves) -> dict[str, float | None]:
    """Per-colour game accuracy, following Lichess's AccuracyPercent.

    ``moves`` are rows with ``colour``, ``eval_before``, ``eval_after`` (mover's point of view) and
    ``classification``, in ply order. Each move's accuracy comes from its drop in winning chances;
    the game score averages a volatility-weighted mean (sharp moments count more) and a harmonic
    mean (one blunder hurts more than in a plain average). A move matching the engine's choice
    counts as 100, as elsewhere in this module. Returns ``{"white": .., "black": ..}``.
    """
    if not moves:
        return {"white": None, "black": None}
    ceil = lambda cp: max(-ACCURACY_CEILING, min(ACCURACY_CEILING, cp))
    sign = lambda m: 1 if m.colour == "white" else -1
    # White's winning chances in every position, including the final one.
    series = [win_percent(ceil(sign(m) * m.eval_before)) for m in moves]
    series.append(win_percent(ceil(sign(moves[-1]) * moves[-1].eval_after)))
    size = max(2, min(8, len(moves) // 10))
    windows = [series[:size]] * (size - 2) + [series[i:i + size] for i in range(len(series) - size + 1)]
    weights = [max(0.5, min(12.0, _std_dev(w))) for w in windows]

    result = {}
    for colour in ("white", "black"):
        scored = []
        for i, m in enumerate(moves):
            if m.colour != colour:
                continue
            before, after = series[i], series[i + 1]
            if colour == "black":
                before, after = 100 - before, 100 - after
            scored.append((100.0 if m.classification == "best" else move_accuracy(before, after), weights[i]))
        if not scored:
            result[colour] = None
            continue
        weighted = sum(a * w for a, w in scored) / sum(w for _, w in scored)
        harmonic = len(scored) / sum(1 / max(a, 0.01) for a, _ in scored)
        result[colour] = round((weighted + harmonic) / 2, 1)
    return result


# ---------------------------------------------------------------------- fingerprints

def _digest(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:16]


def position_key(board: chess.Board) -> str:
    """Exact position, ignoring move counters (so transpositions match)."""
    return _digest(board.epd())


def king_wing(square: chess.Square | None) -> str:
    if square is None:
        return "?"
    file = chess.square_file(square)
    return "queenside" if file <= 2 else "kingside" if file >= 5 else "centre"


def structure(board: chess.Board) -> str:
    """Human-readable pawn structure plus king wings, e.g.
    ``W: c3 d4 e3 f2 g2 h2 (K kingside) | B: c5 d5 e6 f7 g7 h7 (K kingside)``."""
    parts = []
    for colour, label in ((chess.WHITE, "W"), (chess.BLACK, "B")):
        pawns = " ".join(chess.square_name(sq) for sq in sorted(board.pieces(chess.PAWN, colour)))
        parts.append(f"{label}: {pawns or '-'} (K {king_wing(board.king(colour))})")
    return " | ".join(parts)


def structure_key(board: chess.Board) -> str:
    return _digest(structure(board))


# ----------------------------------------------------------------------------- games

@dataclass
class MoveRow:
    ply: int
    move_number: int
    colour: str
    san: str
    uci: str
    fen_before: str
    position_key: str
    structure_key: str
    structure: str
    phase: str
    clock_seconds: float | None
    time_spent_seconds: float | None
    eval_before: int
    eval_after: int
    best_uci: str | None
    best_san: str | None
    best_line: str | None
    cp_loss: int
    win_loss: float
    classification: str
    kind: str | None


@dataclass
class GameAnalysis:
    eco: str | None
    opening: str | None
    moves: list[MoveRow] = field(default_factory=list)


def opening_name(headers: chess.pgn.Headers) -> str | None:
    """Chess.com puts the opening in the ECOUrl header's slug."""
    url = headers.get("ECOUrl") or ""
    slug = url.rstrip("/").rsplit("/", 1)[-1] if "/openings/" in url else ""
    return slug.replace("-", " ").strip() or headers.get("Opening") or None


def parse_time_control(text: str | None) -> tuple[float, float] | None:
    """'180+2' -> (180, 2). Daily games ('1/86400') and unknowns -> None."""
    if not text or "/" in text or text == "-":
        return None
    base, _, inc = text.partition("+")
    try:
        return float(base), float(inc or 0)
    except ValueError:
        return None


def _score(info: dict | None, board: chess.Board) -> int:
    """Eval from White's point of view, in centipawns; terminal positions handled."""
    if board.is_checkmate():
        return -MATE_CP if board.turn == chess.WHITE else MATE_CP
    if board.is_game_over(claim_draw=False):
        return 0
    return info["score"].white().score(mate_score=MATE_CP)


def _clamp(cp: int) -> int:
    return max(-EVAL_CLAMP, min(EVAL_CLAMP, cp))


def _kind(board: chess.Board, move: chess.Move, colour: chess.Color,
          before: int, after: int, best_pv, reply_pv) -> str:
    """Why a bad move was bad: it allowed a tactic, it missed one, or neither."""
    if after <= -MATE_CP + 1_000:
        return "allowed_tactic"            # walked into a forced mate
    if before >= MATE_CP - 1_000:
        return "missed_tactic"             # had a forced mate and let it go
    start = material_balance(board, colour)
    after_board = board.copy(stack=False)
    after_board.push(move)
    if start - balance_after_line(after_board, reply_pv, colour) >= TACTICAL_MATERIAL:
        return "allowed_tactic"            # opponent's best reply wins material
    if best_pv and balance_after_line(board, best_pv, colour) - start >= TACTICAL_MATERIAL:
        return "missed_tactic"             # the engine's move won material
    return "positional"


def analyse_game(pgn_text: str, engine: chess.engine.SimpleEngine,
                 limit: chess.engine.Limit) -> GameAnalysis:
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        raise ValueError("unreadable PGN")
    if game.errors:
        raise ValueError(f"invalid PGN: {game.errors[0]}")
    if game.headers.get("Variant", "Standard") not in ("Standard", ""):
        raise ValueError(f"unsupported variant {game.headers['Variant']}")
    nodes = list(game.mainline())
    tc = parse_time_control(game.headers.get("TimeControl"))

    # Evaluate every position once: positions[i] is the board before ply i+1.
    boards = [game.board()]
    for node in nodes:
        boards.append(node.board())
    infos = []
    for board in boards:
        infos.append(None if board.is_game_over(claim_draw=False) else engine.analyse(board, limit))
    scores = [_score(info, board) for info, board in zip(infos, boards)]

    result = GameAnalysis(eco=game.headers.get("ECO"), opening=opening_name(game.headers))
    last_clock = {chess.WHITE: tc[0] if tc else None, chess.BLACK: tc[0] if tc else None}
    for i, node in enumerate(nodes):
        board, move = boards[i], node.move
        colour = board.turn
        sign = 1 if colour == chess.WHITE else -1
        before, after = sign * scores[i], sign * scores[i + 1]
        best_pv = (infos[i] or {}).get("pv") or []
        reply_pv = (infos[i + 1] or {}).get("pv") or []
        best = best_pv[0] if best_pv else None
        played_best = best == move

        # A move matching the engine's choice loses nothing, whatever depth noise says.
        win_loss = 0.0 if played_best else max(0.0, win_percent(_clamp(before)) - win_percent(_clamp(after)))
        cp_loss = 0 if played_best else max(0, _clamp(before) - _clamp(after))
        label = classify(win_loss, played_best)

        clock = node.clock()
        spent = None
        if clock is not None and last_clock[colour] is not None:
            spent = max(0.0, last_clock[colour] - clock + (tc[1] if tc else 0))
        if clock is not None:
            last_clock[colour] = clock

        result.moves.append(MoveRow(
            ply=i + 1,
            move_number=board.fullmove_number,
            colour="white" if colour == chess.WHITE else "black",
            san=board.san(move),
            uci=move.uci(),
            fen_before=board.fen(),
            position_key=position_key(board),
            structure_key=structure_key(board),
            structure=structure(board),
            phase=phase(board),
            clock_seconds=clock,
            time_spent_seconds=spent,
            eval_before=_clamp(before),
            eval_after=_clamp(after),
            best_uci=best.uci() if best else None,
            best_san=board.san(best) if best else None,
            best_line=board.variation_san(best_pv[:8]) if best_pv else None,
            cp_loss=cp_loss,
            win_loss=round(win_loss, 2),
            classification=label,
            kind=_kind(board, move, colour, before, after, best_pv, reply_pv)
            if label in ("inaccuracy", "mistake", "blunder") else None,
        ))
    return result


# -------------------------------------------------------------------------- database

PENDING_SQL = """
WITH cached AS (
    SELECT DISTINCT ON (COALESCE(x->>'uuid', x->>'url'))
           COALESCE(x->>'uuid', x->>'url') AS id, x->>'pgn' AS pgn
    FROM chess.http_cache c
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(c.payload->'games') = 'array' THEN c.payload->'games' ELSE '[]'::jsonb END) x
    WHERE c.url LIKE 'https://api.chess.com/pub/player/%%/games/%%' AND x->>'pgn' IS NOT NULL
    ORDER BY COALESCE(x->>'uuid', x->>'url'), c.checked_at DESC
)
SELECT g.id, cached.pgn
FROM chess.games g
JOIN cached ON cached.id = g.id
LEFT JOIN chess.analysed_games a ON a.game_id = g.id
WHERE a.game_id IS NULL AND g.rules = 'chess'
  AND (%s = 0 OR g.ended_at >= now() - make_interval(days => %s))
ORDER BY g.ended_at DESC
LIMIT %s
"""

MOVE_COLUMNS = [f for f in MoveRow.__dataclass_fields__]


def ensure_schema(conn) -> None:
    sql = resources.files("collector").joinpath("analysis_schema.sql").read_text()
    with conn.transaction():
        conn.execute(sql)
    fill_missing_accuracy(conn)


@dataclass
class _StoredMove:
    colour: str
    eval_before: int
    eval_after: int
    classification: str


def fill_missing_accuracy(conn) -> int:
    """Work out accuracy for games analysed before accuracy was stored, from their saved moves."""
    ids = [r[0] for r in conn.execute(
        "SELECT game_id FROM chess.analysed_games WHERE status = 'ok' AND white_accuracy IS NULL AND plies > 0")]
    for game_id in ids:
        moves = [_StoredMove(*r) for r in conn.execute(
            """SELECT colour, eval_before, eval_after, classification FROM chess.move_analysis
               WHERE game_id = %s ORDER BY ply""", (game_id,))]
        accuracy = game_accuracy(moves)
        with conn.transaction():
            conn.execute("UPDATE chess.analysed_games SET white_accuracy = %s, black_accuracy = %s WHERE game_id = %s",
                         (accuracy["white"], accuracy["black"], game_id))
    conn.commit()
    if ids:
        log.info("Filled in accuracy for %d previously analysed games", len(ids))
    return len(ids)


def store(conn, game_id: str, analysis: GameAnalysis, engine_name: str, depth: int | None) -> None:
    with conn.transaction():
        conn.execute(
            """INSERT INTO chess.analysed_games
               (game_id, engine, depth, status, eco, opening, plies, white_accuracy, black_accuracy)
               VALUES (%s, %s, %s, 'ok', %s, %s, %s, %s, %s)""",
            (game_id, engine_name, depth, analysis.eco, analysis.opening, len(analysis.moves),
             *game_accuracy(analysis.moves).values()))
        with conn.cursor() as cur:
            cur.executemany(
                f"INSERT INTO chess.move_analysis (game_id, {', '.join(MOVE_COLUMNS)}) "
                f"VALUES (%s, {', '.join(['%s'] * len(MOVE_COLUMNS))})",
                [(game_id, *(getattr(m, c) for c in MOVE_COLUMNS)) for m in analysis.moves])


def store_error(conn, game_id: str, engine_name: str, error: str) -> None:
    """Record a failure so a bad game isn't retried every cycle (delete the row to retry)."""
    with conn.transaction():
        conn.execute(
            """INSERT INTO chess.analysed_games (game_id, engine, status, error)
               VALUES (%s, %s, 'error', %s) ON CONFLICT (game_id) DO NOTHING""",
            (game_id, engine_name, error[:500]))


@dataclass
class Settings:
    stockfish: str = os.environ.get("STOCKFISH_PATH") or shutil.which("stockfish") or "/usr/games/stockfish"
    depth: int = int(os.environ.get("ANALYSIS_DEPTH", "14"))
    max_seconds: float = float(os.environ.get("ANALYSIS_MAX_SECONDS", "1.0"))
    threads: int = int(os.environ.get("ANALYSIS_THREADS", "2"))
    hash_mb: int = int(os.environ.get("ANALYSIS_HASH_MB", "128"))
    batch: int = int(os.environ.get("ANALYSIS_BATCH", "25"))
    days: int = int(os.environ.get("ANALYSIS_DAYS", "30"))  # only games from the last N days; 0 = all

    def limit(self) -> chess.engine.Limit:
        return chess.engine.Limit(depth=self.depth, time=self.max_seconds)


def open_engine(settings: Settings) -> chess.engine.SimpleEngine:
    engine = chess.engine.SimpleEngine.popen_uci(settings.stockfish)
    engine.configure({"Threads": settings.threads, "Hash": settings.hash_mb})
    return engine


LOCK_ID = 48201732  # the collector uses 48201731


def run_batch(conn, engine: chess.engine.SimpleEngine, settings: Settings, limit: int | None = None,
              stop: threading.Event | None = None) -> int:
    """Analyse up to ``limit`` unanalysed games, newest first. Returns games processed."""
    rows = conn.execute(PENDING_SQL, (settings.days, settings.days, limit or settings.batch)).fetchall()
    conn.commit()
    name = engine.id.get("name", "stockfish")
    done = 0
    for game_id, pgn in rows:
        if stop is not None and stop.is_set():
            break
        done += 1
        started = time.monotonic()
        try:
            analysis = analyse_game(pgn, engine, settings.limit())
        except chess.engine.EngineTerminatedError:
            raise  # Stockfish died: don't blame this game, exit so the container restarts
        except (ValueError, chess.engine.EngineError) as exc:
            log.warning("Analysis failed for %s: %s", game_id, exc)
            store_error(conn, game_id, name, str(exc))
            continue
        store(conn, game_id, analysis, name, settings.depth)
        log.info("Analysed %s (%d moves) in %.1fs", game_id, len(analysis.moves), time.monotonic() - started)
    return done


def main(argv=None) -> int:
    import psycopg

    parser = argparse.ArgumentParser(prog="chess-analyse", description=__doc__.splitlines()[0])
    parser.add_argument("--dsn", default=os.environ.get("DATABASE_URL", ""),
                        help="PostgreSQL connection string (default: DATABASE_URL or PG* variables)")
    parser.add_argument("--batch", type=int, help="games per cycle (default: ANALYSIS_BATCH or 25)")
    parser.add_argument("--days", type=int, help="only games from the last N days, 0 for all (default: ANALYSIS_DAYS or 30)")
    parser.add_argument("--all", action="store_true", help="backfill: keep going until nothing is left")
    parser.add_argument("--loop", action="store_true",
                        help="keep running: work through any backlog, then check again every --interval seconds")
    parser.add_argument("--interval", type=int, default=int(os.environ.get("ANALYSIS_INTERVAL", "3600")))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    settings = Settings()
    if args.batch:
        settings.batch = args.batch
    if args.days is not None:
        settings.days = args.days
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    with psycopg.connect(args.dsn) as conn:
        if not conn.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_ID,)).fetchone()[0]:
            log.error("Another chess-analyse is already running; stop it first")
            return 1
        conn.commit()
        ensure_schema(conn)
        with open_engine(settings) as engine:
            log.info("Using %s, depth %d, %d threads", engine.id.get("name"), settings.depth, settings.threads)
            while not stop.is_set():
                done = run_batch(conn, engine, settings, stop=stop)
                while (args.all or args.loop) and done and not stop.is_set():
                    done = run_batch(conn, engine, settings, stop=stop)
                if not args.loop:
                    break
                stop.wait(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
