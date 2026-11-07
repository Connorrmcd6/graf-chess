import json
import os
import pathlib

import chess
import chess.engine
import chess.pgn
import psycopg
import pytest

from collector import analysis

STOCKFISH = analysis.Settings().stockfish
needs_engine = pytest.mark.skipif(not os.path.exists(STOCKFISH), reason="stockfish not installed")
LIMIT = chess.engine.Limit(depth=10)


def test_win_percent_is_symmetric_and_bounded():
    assert analysis.win_percent(0) == pytest.approx(50)
    assert analysis.win_percent(300) == pytest.approx(100 - analysis.win_percent(-300))
    assert 99 < analysis.win_percent(analysis.EVAL_CLAMP) <= 100


def test_classify_thresholds():
    assert analysis.classify(45, True) == "best"
    assert analysis.classify(5, False) == "good"
    assert analysis.classify(12, False) == "inaccuracy"
    assert analysis.classify(25, False) == "mistake"
    assert analysis.classify(31, False) == "blunder"


def _moves(*evals):
    """Rows for alternating white/black moves, each (eval_before, eval_after) from the mover's side."""
    from collector.analysis import _StoredMove
    return [_StoredMove("white" if i % 2 == 0 else "black", b, a, "good") for i, (b, a) in enumerate(evals)]


def test_move_accuracy_matches_lichess_curve():
    assert analysis.move_accuracy(50, 50) == 100
    assert analysis.move_accuracy(50, 60) == 100           # improving is never penalised
    assert analysis.move_accuracy(60, 50) == pytest.approx(64.6, abs=0.1)
    assert analysis.move_accuracy(90, 10) == pytest.approx(1, abs=0.01)  # Lichess adds 1 for imperfect analysis


def test_game_accuracy_rewards_steady_play_and_punishes_a_blunder():
    steady = analysis.game_accuracy(_moves(*[(20, 20), (-20, -20)] * 10))
    assert steady["white"] > 95 and steady["black"] > 95
    # Same game, but White hangs a piece on move 6 (+0.2 -> -3.0).
    blunder = analysis.game_accuracy(_moves(*[(20, 20), (-20, -20)] * 5, (20, -300), (300, 300),
                                            *[(-300, -300), (300, 300)] * 4))
    assert blunder["white"] < steady["white"] - 10
    assert blunder["black"] > 90
    assert analysis.game_accuracy([]) == {"white": None, "black": None}


def test_position_key_matches_transpositions_and_ignores_move_counters():
    a, b = chess.Board(), chess.Board()
    for san in ["d4", "d5", "Bf4", "Nf6", "e3"]:
        a.push_san(san)
    for san in ["d4", "Nf6", "Bf4", "d5", "e3"]:
        b.push_san(san)
    assert analysis.position_key(a) == analysis.position_key(b)
    b.push_san("e6")
    assert analysis.position_key(a) != analysis.position_key(b)


def test_structure_ignores_pieces_but_not_pawns():
    a = chess.Board()
    b = chess.Board()
    for san in ["Nf3", "Nf6", "Nc3", "Nc6"]:
        b.push_san(san)
    assert analysis.structure_key(a) == analysis.structure_key(b)
    b.push_san("d4")
    assert analysis.structure_key(a) != analysis.structure_key(b)
    assert "d4" in analysis.structure(b) and "(K centre)" in analysis.structure(b)


def test_phase():
    board = chess.Board()
    assert analysis.phase(board) == "opening"
    board.set_fen("4k3/pp3ppp/8/8/8/8/PP3PPP/3RK3 w - - 0 30")
    assert analysis.phase(board) == "endgame"
    board.set_fen("r1bq1rk1/pp3ppp/2n2n2/3p4/3P4/2N2N2/PP3PPP/R1BQ1RK1 w - - 0 15")
    assert analysis.phase(board) == "middlegame"


def test_balance_after_line_finishes_exchanges():
    board = chess.Board("4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1")
    line = [chess.Move.from_uci("e4d5")]
    assert analysis.balance_after_line(board, line, chess.WHITE, plies=0) == 1


def test_time_control_and_opening_name():
    assert analysis.parse_time_control("180+2") == (180, 2)
    assert analysis.parse_time_control("600") == (600, 0)
    assert analysis.parse_time_control("1/86400") is None
    headers = chess.pgn.Game().headers
    headers["ECOUrl"] = "https://www.chess.com/openings/Pirc-Defense-Austrian-Attack"
    assert analysis.opening_name(headers) == "Pirc Defense Austrian Attack"


@needs_engine
def test_hanging_the_queen_is_a_tactical_blunder():
    pgn = '[TimeControl "180+2"]\n\n1. e4 { [%clk 0:02:58] } e5 { [%clk 0:02:59] } 2. Qh5 { [%clk 0:02:55] } ' \
          'Nc6 { [%clk 0:02:50] } 3. Qxf7+ { [%clk 0:02:50] } *'
    with chess.engine.SimpleEngine.popen_uci(STOCKFISH) as engine:
        result = analysis.analyse_game(pgn, engine, LIMIT)
    last = result.moves[-1]
    assert last.san == "Qxf7+" and last.classification == "blunder" and last.kind == "allowed_tactic"
    assert result.moves[0].time_spent_seconds == pytest.approx(4)  # 180 - 178 + 2


@needs_engine
def test_missing_mate_in_one_is_a_missed_tactic():
    pgn = '[SetUp "1"]\n[FEN "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1"]\n\n1. Kf2 *'
    with chess.engine.SimpleEngine.popen_uci(STOCKFISH) as engine:
        move = analysis.analyse_game(pgn, engine, LIMIT).moves[0]
    # Still a rook up afterwards, so winning chances barely drop - but it is flagged as a missed tactic.
    assert move.best_san == "Ra8#" and move.classification == "inaccuracy" and move.kind == "missed_tactic"


@needs_engine
def test_checkmate_position_needs_no_engine_call():
    pgn = "1. f3 e5 2. g4 Qh4# 0-1"
    with chess.engine.SimpleEngine.popen_uci(STOCKFISH) as engine:
        moves = analysis.analyse_game(pgn, engine, LIMIT).moves
    assert moves[-1].san == "Qh4#" and moves[-1].eval_after == analysis.EVAL_CLAMP
    assert moves[2].classification == "blunder"  # 2. g4??


# --------------------------------------------------------------- database round trip

@needs_engine
def test_pipeline_finds_repeated_mistake(db, database_url):
    from psycopg.types.json import Jsonb

    archive = json.loads((pathlib.Path(__file__).parent / "fixtures" / "london_archive.json").read_text())
    db.execute("INSERT INTO chess.http_cache (url, payload) VALUES (%s, %s)",
               ("https://api.chess.com/pub/player/alice/games/2025/10", Jsonb(archive)))
    for game in archive["games"]:
        db.execute("INSERT INTO chess.games VALUES (%s, %s, to_timestamp(%s), true, 'chess', 'blitz', '180+2')",
                   (game["uuid"], game["url"], game["end_time"]))
        db.execute("INSERT INTO chess.performances VALUES (%s, 'alice', 'white', 900, 'x', 900, 'win', 'win', null)",
                   (game["uuid"],))

    analysis.ensure_schema(db)
    analysis.ensure_schema(db)  # re-running on startup is harmless
    settings = analysis.Settings(depth=10, max_seconds=0.2, threads=1)
    with analysis.open_engine(settings) as engine:
        settings.days = 30
        assert analysis.run_batch(db, engine, settings) == 0  # the fixture games are from 2025
        settings.days = 0
        assert analysis.run_batch(db, engine, settings, limit=2) == 2
        assert analysis.run_batch(db, engine, settings) == 3
        assert analysis.run_batch(db, engine, settings) == 0

    status = db.execute("SELECT games, analysed, failed FROM dashboard.analysis_status WHERE username = 'alice'").fetchone()
    assert status == (5, 5, 0)
    # Only White's (the tracked player's) moves appear.
    assert db.execute("SELECT DISTINCT colour FROM dashboard.player_moves").fetchall() == [("white",)]
    repeated = db.execute(
        "SELECT your_move, times_played, opening FROM dashboard.repeated_mistakes WHERE your_move = 'Bd3'").fetchone()
    assert repeated is not None and repeated[1] == 5 and repeated[2].startswith("London System")
    position = db.execute(
        "SELECT games, usual_move FROM dashboard.repeated_positions WHERE move_number = 5").fetchone()
    assert position == (5, "Bd3")

    # Every analysed game gets an accuracy for each side; the tracked player's shows in recent_games.
    accuracy = db.execute("SELECT min(white_accuracy), max(white_accuracy), count(black_accuracy) FROM chess.analysed_games").fetchone()
    assert 0 < accuracy[0] <= accuracy[1] <= 100 and accuracy[2] == 5
    recent = db.execute("SELECT stockfish_accuracy, chesscom_accuracy, blunders + mistakes + inaccuracies FROM dashboard.recent_games").fetchall()
    assert len(recent) == 5 and all(r[0] is not None and r[1] is None and r[2] > 0 for r in recent)
    # Games analysed before accuracy existed are filled in from their stored moves on the next start.
    before = db.execute("SELECT game_id, white_accuracy FROM chess.analysed_games ORDER BY game_id").fetchall()
    db.execute("UPDATE chess.analysed_games SET white_accuracy = NULL, black_accuracy = NULL")
    analysis.ensure_schema(db)
    assert db.execute("SELECT game_id, white_accuracy FROM chess.analysed_games ORDER BY game_id").fetchall() == before

    # Grafana's read-only role sees the analysis views but not the raw tables.
    with psycopg.connect(database_url.replace("chess_owner", "grafana_reader"), autocommit=True) as reader:
        for view in ("player_moves", "repeated_mistakes", "repeated_positions", "structure_mistakes",
                     "errors", "analysis_status", "recent_games"):
            reader.execute(f"SELECT * FROM dashboard.{view} LIMIT 1")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            reader.execute("SELECT * FROM chess.move_analysis")


def test_illegal_move_rejects_the_game_instead_of_analysing_half_of_it():
    with pytest.raises(ValueError, match="invalid PGN"):
        analysis.analyse_game("1. e4 e5 2. Ke3 *", None, LIMIT)  # illegal move: rejected before the engine runs
