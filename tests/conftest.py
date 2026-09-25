import subprocess
import time
from datetime import datetime, timezone

import psycopg
import pytest

from collector.main import initialize


def pytest_addoption(parser):
    parser.addoption("--integration", action="store_true", help="Start a disposable Docker PostgreSQL for integration tests")


@pytest.fixture
def config():
    return {
        "name": "Test competition", "start": datetime(2026, 8, 7, 22, tzinfo=timezone.utc),
        "end": datetime(2026, 10, 30, 22, tzinfo=timezone.utc), "timezone": "Africa/Johannesburg",
        "minimum_games": 20,
        "players": [{"username": "alice", "name": "Alice"}, {"username": "bob", "name": "Bob"}],
    }


@pytest.fixture(scope="session")
def database_url(request):
    if not request.config.getoption("--integration"):
        pytest.skip("Pass --integration to run disposable PostgreSQL tests")
    container = subprocess.check_output([
        "docker", "run", "--rm", "--detach", "-e", "POSTGRES_PASSWORD=test-only",
        "-p", "127.0.0.1::5432", "postgres:17-alpine",
    ], text=True).strip()
    try:
        port = subprocess.check_output(["docker", "port", container, "5432"], text=True).strip().rsplit(":", 1)[1]
        admin_url = f"postgresql://postgres:test-only@127.0.0.1:{port}/postgres"
        for _ in range(60):
            try:
                with psycopg.connect(admin_url, autocommit=True) as connection:
                    connection.execute("CREATE ROLE chess_owner LOGIN PASSWORD 'test-only'")
                    connection.execute("CREATE ROLE grafana_reader LOGIN PASSWORD 'test-only'")
                    connection.execute("GRANT CREATE ON DATABASE postgres TO chess_owner")
                    connection.execute("ALTER ROLE grafana_reader SET default_transaction_read_only = on")
                break
            except psycopg.OperationalError:
                time.sleep(0.5)
        else:
            raise RuntimeError("Disposable PostgreSQL did not start")
        yield f"postgresql://chess_owner:test-only@127.0.0.1:{port}/postgres"
    finally:
        subprocess.run(["docker", "stop", container], capture_output=True, check=True)


@pytest.fixture
def db(database_url, config):
    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute("DROP SCHEMA IF EXISTS dashboard CASCADE")
        connection.execute("DROP SCHEMA IF EXISTS chess CASCADE")
        initialize(connection, config)
        yield connection


@pytest.fixture
def game(config):
    def make(number=1, username="alice", rating=1000, opponent="outsider", **changes):
        value = {
            "uuid": f"game-{number}", "url": f"https://www.chess.com/game/live/{number}",
            "end_time": int(config["start"].timestamp()) + number,
            "rated": True, "rules": "chess", "time_class": "rapid", "time_control": "600",
            "white": {"username": username, "rating": rating, "result": "win"},
            "black": {"username": opponent, "rating": 900, "result": "resigned"},
        }
        value.update(changes)
        return value
    return make
