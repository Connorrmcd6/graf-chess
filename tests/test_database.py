from datetime import timedelta
from io import BytesIO
from urllib.error import HTTPError

import psycopg
import pytest

from collector.api import ChessAPI
from collector.main import finalize, health, import_games, initialize, sync


def standings(db):
    return {row[0]: row[1:] for row in db.execute(
        "SELECT username, rating, games, qualified, rank FROM dashboard.standings"
    )}


def test_qualification_ties_and_duplicate_imports(db, game):
    games = [game(i) for i in range(1, 20)]
    import_games(db, games, {"alice", "bob"})
    assert standings(db)["alice"] == (1000, 19, False, None)
    import_games(db, games + [game(20)], {"alice", "bob"})
    import_games(db, [game(i, username="bob") for i in range(21, 41)], {"alice", "bob"})
    assert standings(db)["alice"] == (1000, 20, True, 1)
    assert standings(db)["bob"] == (1000, 20, True, 1)
    assert db.execute("SELECT count(*) FROM chess.games").fetchone()[0] == 40


def test_boundaries_latest_not_peak_and_empty_players(db, game, config):
    start, end = int(config["start"].timestamp()), int(config["end"].timestamp())
    games = [game(1, end_time=start - 1, rating=1900), game(2, end_time=start, rating=1500),
             game(3, end_time=end - 1, rating=1200), game(4, end_time=end, rating=2000),
             game(5, rated=False), game(6, rules="chess960"), game(7, time_class="blitz")]
    import_games(db, games, {"alice", "bob"})
    assert standings(db)["alice"] == (1200, 2, False, None)
    assert standings(db)["bob"] == (None, 0, False, None)


def test_shared_game_and_late_accuracy(db, game):
    shared = game(opponent="bob")
    import_games(db, [shared, shared], {"alice", "bob"})
    assert db.execute("SELECT count(*) FROM chess.games").fetchone()[0] == 1
    assert db.execute("SELECT count(*) FROM chess.performances").fetchone()[0] == 2
    updated = dict(shared, accuracies={"white": 80.2, "black": 62.4})
    import_games(db, [updated, shared], {"alice", "bob"})
    assert db.execute("SELECT accuracy FROM chess.performances WHERE username = 'alice'").fetchone()[0] == 80.2


def test_finalization_requires_refresh_then_freezes_standings(db, game, config):
    import_games(db, [game(i) for i in range(1, 21)], {"alice", "bob"})
    with pytest.raises(ValueError, match="24 hours"):
        finalize(db, config["end"])
    after = config["end"] + timedelta(days=2)
    with pytest.raises(ValueError, match="full refresh"):
        finalize(db, after)
    db.execute("INSERT INTO chess.sync_runs (full_refresh, success, started_at, finished_at) VALUES (true, true, %s, %s)", (after, after))
    finalize(db, after)
    import_games(db, [game(20, rating=2000)], {"alice", "bob"})
    assert standings(db)["alice"][0] == 1000
    assert db.execute("SELECT rating FROM dashboard.live_standings WHERE username = 'alice'").fetchone()[0] == 2000
    with pytest.raises(ValueError, match="already finalized"):
        finalize(db, after)


def test_reader_can_only_read_dashboard_views(db, database_url):
    with psycopg.connect(database_url.replace("chess_owner", "grafana_reader"), autocommit=True) as reader:
        assert reader.execute("SELECT count(*) FROM dashboard.players").fetchone()[0] == 2
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            reader.execute("SELECT * FROM chess.http_cache")
        assert reader.execute("SHOW default_transaction_read_only").fetchone()[0] == "on"
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            reader.execute("DELETE FROM dashboard.players")
        reader.execute("SET default_transaction_read_only = off")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            reader.execute("DELETE FROM dashboard.players")


def test_configuration_drift_is_rejected(db, config):
    initialize(db, config)
    changed = dict(config, minimum_games=10)
    with pytest.raises(ValueError, match="differs"):
        initialize(db, changed)


class FakeAPI:
    def __init__(self, games, fail=False):
        self.games = games
        self.fail = fail

    def get(self, url):
        if url.endswith("/stats"):
            return {"chess_rapid": {"last": {"rating": 1000, "date": self.games[0]["end_time"]}}}
        if url.endswith("/archives"):
            if self.fail and "/alice/" in url:
                raise RuntimeError("API unavailable")
            return {"archives": [url.removesuffix("/archives") + "/2026/08"]}
        return {"games": self.games}


def test_failed_player_retains_data_and_other_players_continue(db, game, config):
    api = FakeAPI([game()])
    now = config["start"] + timedelta(days=5)
    assert sync(db, config, api=api, now=now)
    before = db.execute("SELECT last_success_at FROM chess.player_sync WHERE username = 'alice'").fetchone()[0]
    assert not sync(db, config, api=FakeAPI([game()], fail=True), now=now)
    assert health(db)
    after, error = db.execute("SELECT last_success_at, error FROM chess.player_sync WHERE username = 'alice'").fetchone()
    assert before == after
    assert error == "API unavailable"
    assert standings(db)["alice"][1] == 1
    assert db.execute("SELECT error FROM chess.player_sync WHERE username = 'bob'").fetchone()[0] is None


def test_http_cache_and_rate_limit_retry(db):
    response = BytesIO(b'{"games": []}')
    response.headers = {"ETag": '"version1"', "Last-Modified": "Mon, 01 Jan 2026 00:00:00 GMT"}
    requests, delays = [], []
    replies = [HTTPError("url", 429, "rate limit", {"Retry-After": "1"}, None), response,
               HTTPError("url", 304, "not modified", {}, None)]

    def opener(request, timeout):
        requests.append(request)
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    api = ChessAPI(db, "test/1", opener=opener, sleeper=delays.append)
    assert api.get("https://api.chess.com/pub/player/alice/games/2026/08") == {"games": []}
    assert api.get("https://api.chess.com/pub/player/alice/games/2026/08") == {"games": []}
    assert delays == [1]
    assert requests[-1].get_header("If-none-match") == '"version1"'
