import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen

import psycopg
import pytest

from collector import analysis, web

FEN = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


def test_board_svg_draws_both_arrows_and_rejects_bad_input():
    svg = web.board_svg(FEN, "black", "e7e5", "c7c5")
    assert svg.startswith("<svg") and svg.count("arrow") >= 2
    for args in (("not a fen",), (FEN, "white", "e7e5; drop table"), (FEN, "white", "", "zz99")):
        with pytest.raises(web.BadRequest):
            web.board_svg(*args)


def _seed(db):
    """Two games for alice that both reach the same position and repeat the same mistake there."""
    analysis.ensure_schema(db)
    for n in (1, 2):
        db.execute("INSERT INTO chess.games VALUES (%s, %s, now() - make_interval(days => %s), true, 'chess', 'rapid', '600')",
                   (f"g{n}", f"https://www.chess.com/game/live/{n}", n))
        db.execute("INSERT INTO chess.performances VALUES (%s, 'alice', 'black', 900, 'opp', 900, 'loss', 'loss', 70)", (f"g{n}",))
        db.execute("""INSERT INTO chess.analysed_games (game_id, status, opening, plies, white_accuracy, black_accuracy)
                      VALUES (%s, 'ok', 'Kings Pawn Opening', 1, 95, 61.5)""", (f"g{n}",))
        db.execute("""INSERT INTO chess.move_analysis (game_id, ply, move_number, colour, san, uci, fen_before, position_key,
                      structure_key, structure, phase, clock_seconds, eval_before, eval_after, best_uci, best_san, best_line,
                      cp_loss, win_loss, classification, kind)
                      VALUES (%s, 2, 1, 'black', 'f6', 'f7f6', %s, 'pos1', 's1', 's', 'opening', 590, 0, -150, 'e7e5', 'e5',
                      '1... e5 2. Nf3', 150, 24, 'mistake', 'positional')""", (f"g{n}", FEN))


@pytest.fixture
def app(db, database_url):
    _seed(db)
    reader = database_url.replace("chess_owner", "grafana_reader")
    return web.App(lambda: psycopg.connect(reader, autocommit=True), cache_seconds=0)


def test_api_reads_everything_through_the_read_only_role(app):
    q = {"player": "alice", "mode": "all"}
    overview = app.get("/api/overview", q)
    assert overview["summary"]["games"] == 2 and overview["summary"]["accuracy"] == 61.5
    [repeat] = overview["repeated"]
    assert (repeat["san"], repeat["best_san"], repeat["times"], repeat["uci"], repeat["best_uci"]) == ("f6", "e5", 2, "f7f6", "e7e5")
    errors = app.get("/api/errors", q)
    assert len(errors["errors"]) == 2 and errors["more"] is False and errors["errors"][0]["fen"] == FEN
    [drill] = app.get("/api/drill", q)["positions"]
    assert drill["repeated"] is True
    games = app.get("/api/games", q)["games"]
    assert [g["game_id"] for g in games] == ["g1", "g2"] and games[0]["chesscom_accuracy"] == 70
    game = app.get("/api/game", q | {"id": "g1"})
    assert game["game"]["blunders"] == 0 and len(game["errors"]) == 1
    assert app.get("/api/errors", q | {"mode": "blitz"})["errors"] == []


def test_api_rejects_unknown_player_mode_and_game(app):
    for q in ({"player": "mallory"}, {"player": "alice", "mode": "chess960"}, {"player": "alice", "offset": "x"}):
        with pytest.raises(web.BadRequest):
            app.get("/api/overview", q)
    with pytest.raises(web.BadRequest):
        app.get("/api/game", {"player": "alice", "id": "nope"})
    with pytest.raises(web.NotFound):
        app.get("/api/nope", {"player": "alice"})


def test_http_server_serves_pages_boards_and_json(app):
    server = ThreadingHTTPServer(("127.0.0.1", 0), web.make_handler(app))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        for path in ("/", "/review", "/drill", "/games", "/game", "/static/app.js", "/static/manifest.json", "/sw.js"):
            with urlopen(base + path) as r:
                assert r.status == 200 and r.headers["X-Frame-Options"] == "DENY"
                assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
        with urlopen(f"{base}/board.svg?fen={FEN.replace(' ', '+')}&o=black&you=f7f6&best=e7e5") as r:
            assert r.headers["Content-Type"] == "image/svg+xml" and "immutable" in r.headers["Cache-Control"]
        with urlopen(base + "/api/players") as r:
            assert [p["username"] for p in json.load(r)["players"]] == ["alice", "bob"]
        for path in ("/board.svg?fen=bad", "/api/overview?player=mallory", "/static/../web.py", "/nope"):
            with pytest.raises(HTTPError) as e:
                urlopen(base + path)
            assert e.value.code in (400, 404)
    finally:
        server.shutdown()


def test_api_answers_are_cached_briefly(db, database_url):
    _seed(db)
    calls = []
    reader = database_url.replace("chess_owner", "grafana_reader")

    def connect():
        calls.append(1)
        return psycopg.connect(reader, autocommit=True)

    app = web.App(connect, cache_seconds=60)
    first = app.get("/api/games", {"player": "alice"})
    assert app.get("/api/games", {"player": "alice"}) is first and len(calls) == 1
    app.get("/api/games", {"player": "alice", "mode": "rapid"})
    assert len(calls) == 2
    assert web.App(connect, cache_seconds=0).get("/api/players", {}) and len(calls) == 3
