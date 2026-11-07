"""Phone-first web app for the engine analysis: recurring mistakes, a review feed, a drill and recent games.

Read-only: it connects as Grafana's read-only database role and only queries ``dashboard`` views.
Boards are rendered server-side as SVG with python-chess, so the pages need no chess JavaScript.
"""
from __future__ import annotations

import argparse
import json
import logging
import mimetypes
import os
import re
import threading
import time
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import chess
import chess.svg

log = logging.getLogger(__name__)
STATIC = Path(__file__).with_name("static")
PAGES = {"/": "index.html", "/review": "review.html", "/drill": "drill.html", "/games": "games.html",
         "/game": "game.html", "/sw.js": "sw.js"}
MODES = ("rapid", "blitz", "bullet", "daily")
PAGE_SIZE = 20
UCI = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$")
COLOURS = {"square light": "#efe4d2", "square dark": "#b98b62", "margin": "#00000000", "coord": "#6f655a"}
RED, GREEN = "#d0432bcc", "#2f8a50cc"


class BadRequest(ValueError):
    pass


class NotFound(Exception):
    pass


# ----------------------------------------------------------------------------- boards

@lru_cache(maxsize=2048)
def board_svg(fen: str, orientation: str = "white", you: str = "", best: str = "") -> str:
    """The position with your move as a red arrow and the engine's as a green one."""
    try:
        board = chess.Board(fen)
    except ValueError:
        raise BadRequest("bad position")
    arrows = []
    for uci, colour in ((you, RED), (best, GREEN)):
        if not uci:
            continue
        if not UCI.match(uci):
            raise BadRequest("bad move")
        move = chess.Move.from_uci(uci)
        arrows.append(chess.svg.Arrow(move.from_square, move.to_square, color=colour))
    if you and best and you == best:
        arrows = arrows[1:]
    return chess.svg.board(board, orientation=orientation != "black", arrows=arrows, colors=COLOURS, coordinates=True,
                           check=board.king(board.turn) if board.is_check() else None)


# ------------------------------------------------------------------------------- data

MOVE_FIELDS = """game_id, url, ended_at, mode, opening, colour, move_number, san, uci, best_san, best_uci, best_line,
                 fen_before AS fen, classification, kind, win_loss, eval_before, eval_after, clock_seconds, phase"""

# Layer 1, with mode filtering: the same bad move from the same position, in 2+ games.
REPEATED_SQL = f"""
SELECT position_key, san, min(uci) AS uci, count(DISTINCT game_id) AS times,
       mode() WITHIN GROUP (ORDER BY best_san) AS best_san, mode() WITHIN GROUP (ORDER BY best_uci) AS best_uci,
       round(avg(win_loss)::numeric, 1) AS avg_drop, mode() WITHIN GROUP (ORDER BY kind) AS kind,
       mode() WITHIN GROUP (ORDER BY opening) AS opening, min(move_number) AS move_number, min(colour) AS colour,
       min(fen_before) AS fen, (array_agg(url ORDER BY ended_at DESC))[1] AS url
FROM dashboard.player_moves WHERE username = %(player)s AND mode = ANY(%(modes)s) AND is_error
GROUP BY position_key, san HAVING count(DISTINCT game_id) >= 2
ORDER BY count(DISTINCT game_id) * avg(win_loss) DESC LIMIT 20"""

# Positions reached in 3+ games and misplayed at least twice; shows the most common wrong move.
POSITIONS_SQL = """
SELECT position_key, count(DISTINCT game_id) AS games, count(*) FILTER (WHERE is_error) AS errors,
       mode() WITHIN GROUP (ORDER BY san) FILTER (WHERE is_error) AS wrong_san,
       mode() WITHIN GROUP (ORDER BY uci) FILTER (WHERE is_error) AS wrong_uci,
       mode() WITHIN GROUP (ORDER BY best_san) AS best_san, mode() WITHIN GROUP (ORDER BY best_uci) AS best_uci,
       round(avg(win_loss) FILTER (WHERE is_error)::numeric, 1) AS avg_drop,
       mode() WITHIN GROUP (ORDER BY opening) AS opening, min(move_number) AS move_number, min(colour) AS colour,
       min(fen_before) AS fen
FROM dashboard.player_moves WHERE username = %(player)s AND mode = ANY(%(modes)s)
GROUP BY position_key HAVING count(DISTINCT game_id) >= 3 AND count(*) FILTER (WHERE is_error) >= 2
ORDER BY count(*) FILTER (WHERE is_error) DESC, count(DISTINCT game_id) DESC LIMIT 20"""

SUMMARY_SQL = """
SELECT count(DISTINCT game_id) AS games, count(*) AS moves,
       round(100.0 * count(*) FILTER (WHERE is_error) / nullif(count(*), 0), 1) AS errors_per_100,
       count(*) FILTER (WHERE classification = 'blunder') AS blunders,
       round(100.0 * count(*) FILTER (WHERE kind = 'positional') / nullif(count(*) FILTER (WHERE is_error), 0)) AS positional_pct
FROM dashboard.player_moves WHERE username = %(player)s AND mode = ANY(%(modes)s)"""

ACCURACY_SQL = """
SELECT round(avg(stockfish_accuracy)::numeric, 1) AS accuracy, round(avg(chesscom_accuracy)::numeric, 1) AS chesscom
FROM dashboard.recent_games WHERE username = %(player)s AND mode = ANY(%(modes)s) AND stockfish_accuracy IS NOT NULL"""

BREAKDOWN_SQL = """
SELECT {key} AS label, count(*) AS moves, round(100.0 * count(*) FILTER (WHERE is_error) / count(*), 1) AS rate
FROM dashboard.player_moves WHERE username = %(player)s AND mode = ANY(%(modes)s) AND {key} IS NOT NULL
GROUP BY {key} ORDER BY {order}"""

OPENINGS_SQL = """
SELECT opening AS label, count(DISTINCT game_id) AS games,
       round(count(*) FILTER (WHERE is_error)::numeric / count(DISTINCT game_id), 1) AS per_game
FROM dashboard.player_moves WHERE username = %(player)s AND mode = ANY(%(modes)s) AND opening IS NOT NULL
GROUP BY opening HAVING count(DISTINCT game_id) >= 3 ORDER BY per_game DESC LIMIT 6"""

ERRORS_SQL = f"""
SELECT {MOVE_FIELDS} FROM dashboard.errors
WHERE username = %(player)s AND mode = ANY(%(modes)s) AND classification = ANY(%(classes)s)
ORDER BY ended_at DESC, ply LIMIT %(limit)s OFFSET %(offset)s"""

DRILL_SQL = f"""
WITH repeated AS (
    SELECT position_key FROM dashboard.player_moves
    WHERE username = %(player)s AND mode = ANY(%(modes)s) AND is_error
    GROUP BY position_key HAVING count(DISTINCT game_id) >= 2
)
, candidates AS (
    SELECT DISTINCT ON (position_key) {MOVE_FIELDS}, position_key,
           position_key IN (SELECT position_key FROM repeated) AS repeated
    FROM dashboard.errors
    WHERE username = %(player)s AND mode = ANY(%(modes)s)
      AND (classification IN ('mistake', 'blunder') OR position_key IN (SELECT position_key FROM repeated))
    ORDER BY position_key, win_loss DESC
)
SELECT * FROM candidates ORDER BY repeated DESC, ended_at DESC LIMIT 60"""

GAMES_SQL = """
SELECT game_id, url, ended_at, mode, time_control, colour, opponent, opponent_rating, rating, outcome, opening,
       stockfish_accuracy, chesscom_accuracy, blunders, mistakes, inaccuracies
FROM dashboard.recent_games WHERE username = %(player)s AND mode = ANY(%(modes)s) AND rules = 'chess'
ORDER BY ended_at DESC LIMIT %(limit)s OFFSET %(offset)s"""

GAME_SQL = """
SELECT game_id, url, ended_at, mode, time_control, colour, opponent, opponent_rating, rating, outcome, opening,
       stockfish_accuracy, chesscom_accuracy, blunders, mistakes, inaccuracies
FROM dashboard.recent_games WHERE username = %(player)s AND game_id = %(game)s"""

GAME_ERRORS_SQL = f"""
SELECT {MOVE_FIELDS} FROM dashboard.errors WHERE username = %(player)s AND game_id = %(game)s ORDER BY ply"""


def rows(conn, sql: str, params: dict) -> list[dict]:
    cur = conn.execute(sql, params)
    names = [c.name for c in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


CACHE_SECONDS = 60          # identical API requests within this window are answered from memory
MAX_DB_REQUESTS = 4         # Grafana's read-only role allows 10 connections; leave most of them for Grafana
CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self'; "
       "connect-src 'self'; manifest-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")


class App:
    """Public and read-only, so API answers are cached briefly and database use is capped."""

    def __init__(self, connect, cache_seconds: float = CACHE_SECONDS):
        self.connect = connect
        self.cache_seconds = cache_seconds
        self._cache: dict[tuple, tuple[float, dict]] = {}
        self._lock = threading.Lock()
        self._db = threading.BoundedSemaphore(MAX_DB_REQUESTS)

    def get(self, path: str, q: dict) -> dict:
        key = (path, tuple(sorted(q.items())))
        now = time.monotonic()
        with self._lock:
            hit = self._cache.get(key)
            if hit and now - hit[0] < self.cache_seconds:
                return hit[1]
        with self._db:
            result = self._query(path, q)
        with self._lock:
            if len(self._cache) > 500:  # unique queries are bounded by players x modes x pages; keep it small anyway
                self._cache.clear()
            self._cache[key] = (now, result)
        return result

    def params(self, q: dict, conn) -> dict:
        player = q.get("player", "")
        if not conn.execute("SELECT 1 FROM dashboard.players WHERE username = %s", (player,)).fetchone():
            raise BadRequest("unknown player")
        mode = q.get("mode") or "all"
        if mode != "all" and mode not in MODES:
            raise BadRequest("unknown mode")
        try:
            offset = max(0, int(q.get("offset") or 0))
        except ValueError:
            raise BadRequest("bad offset")
        return {"player": player, "modes": list(MODES) if mode == "all" else [mode], "offset": offset, "limit": PAGE_SIZE}

    def _query(self, path: str, q: dict) -> dict:
        with self.connect() as conn:
            if path == "/api/players":
                return {"players": rows(conn, """SELECT p.username, p.name, coalesce(s.analysed, 0) AS analysed
                    FROM dashboard.players p LEFT JOIN dashboard.analysis_status s USING (username) ORDER BY p.name""", {})}
            p = self.params(q, conn)
            if path == "/api/overview":
                return {
                    "summary": rows(conn, SUMMARY_SQL, p)[0] | rows(conn, ACCURACY_SQL, p)[0],
                    "repeated": rows(conn, REPEATED_SQL, p),
                    "positions": rows(conn, POSITIONS_SQL, p),
                    "phases": rows(conn, BREAKDOWN_SQL.format(
                        key="phase", order="array_position(ARRAY['opening','middlegame','endgame'], phase)"), p),
                    "clock": rows(conn, BREAKDOWN_SQL.format(
                        key="clock_bucket", order="array_position(ARRAY['3min+','1-3min','30-60s','10-30s','0-10s'], clock_bucket)"), p),
                    "openings": rows(conn, OPENINGS_SQL, p),
                }
            if path == "/api/errors":
                kind = q.get("kind") or "serious"
                classes = {"serious": ["mistake", "blunder"], "blunder": ["blunder"],
                           "all": ["inaccuracy", "mistake", "blunder"]}.get(kind)
                if classes is None:
                    raise BadRequest("unknown kind")
                items = rows(conn, ERRORS_SQL, p | {"classes": classes, "limit": PAGE_SIZE + 1})
                return {"errors": items[:PAGE_SIZE], "more": len(items) > PAGE_SIZE}
            if path == "/api/drill":
                positions = rows(conn, DRILL_SQL, p)
                for item in positions:  # lets the page offer tap-to-move without a chess library in the browser
                    board = chess.Board(item["fen"])
                    item["legal"] = {m.uci(): board.san(m) for m in board.legal_moves}
                return {"positions": positions}
            if path == "/api/games":
                items = rows(conn, GAMES_SQL, p | {"limit": PAGE_SIZE + 1})
                return {"games": items[:PAGE_SIZE], "more": len(items) > PAGE_SIZE}
            if path == "/api/game":
                game = rows(conn, GAME_SQL, p | {"game": q.get("id", "")})
                if not game:
                    raise BadRequest("unknown game")
                return {"game": game[0], "errors": rows(conn, GAME_ERRORS_SQL, p | {"game": q.get("id", "")})}
        raise NotFound(path)


def _default(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            if url.path in PAGES:
                return self._file(STATIC / PAGES[url.path])
            if url.path.startswith("/static/"):
                name = url.path.removeprefix("/static/")
                path = STATIC / name
                if "/" in name or not path.is_file():
                    return self._send(404, "text/plain", b"not found")
                return self._file(path)
            if url.path == "/board.svg":
                try:
                    svg = board_svg(q.get("fen", ""), q.get("o", "white"), q.get("you", ""), q.get("best", ""))
                except BadRequest as e:
                    return self._send(400, "text/plain", str(e).encode())
                return self._send(200, "image/svg+xml", svg.encode(), "public, max-age=604800, immutable")
            if url.path == "/healthz":
                return self._send(200, "text/plain", b"ok")
            if url.path.startswith("/api/"):
                return self._api(lambda: app.get(url.path, q))
            self._send(404, "text/plain", b"not found")

        def _api(self, call):
            try:
                self._send(200, "application/json", json.dumps(call(), default=_default).encode())
            except NotFound:
                self._send(404, "application/json", b'{"error": "not found"}')
            except BadRequest as e:
                self._send(400, "application/json", json.dumps({"error": str(e)}).encode())
            except Exception:
                log.exception("request failed: %s", self.path)
                self._send(500, "application/json", b'{"error": "server error, see the logs"}')

        def _file(self, path: Path):
            kind = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            if path.suffix == ".json":
                kind = "application/manifest+json"
            if kind.startswith("text/") or kind.endswith("javascript"):
                kind += "; charset=utf-8"
            self._send(200, kind, path.read_bytes())

        def _send(self, code: int, content_type: str, body: bytes, cache: str = "no-store"):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", cache)
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", CSP)
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    return Handler


def main(argv=None) -> int:
    import psycopg

    parser = argparse.ArgumentParser(prog="chess-web", description=__doc__.splitlines()[0])
    parser.add_argument("command", nargs="?", choices=["run", "health"], default="run")
    parser.add_argument("--host", default=os.environ.get("WEB_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("WEB_PORT", "8083")))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.command == "health":
        from urllib.request import urlopen
        try:
            with urlopen(f"http://127.0.0.1:{args.port}/healthz", timeout=5) as r:
                return 0 if r.status == 200 else 1
        except OSError:
            return 1
    dsn = os.environ.get("DATABASE_URL", "")
    server = ThreadingHTTPServer((args.host, args.port), make_handler(App(lambda: psycopg.connect(dsn, autocommit=True))))
    log.info("chess web on http://%s:%d", args.host, args.port)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
