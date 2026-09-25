import argparse
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def compose(*args, **kwargs):
    return subprocess.run(["docker", "compose", *args], cwd=ROOT, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description="Back up chess data and optionally verify a restore in a temporary database")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    directory = ROOT / "backups"
    directory.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"chess-{stamp}.dump"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as file:
        compose("exec", "-T", "db", "pg_dump", "-U", "chess_owner", "-d", "chess", "--format=custom", "--no-owner", stdout=file)
    if args.verify:
        database = "restore_check_" + uuid.uuid4().hex[:12]
        compose("exec", "-T", "db", "createdb", "-U", "postgres", "--owner=chess_owner", database)
        try:
            with path.open("rb") as file:
                compose("exec", "-T", "db", "pg_restore", "-U", "chess_owner", "-d", database,
                        "--no-owner", "--exit-on-error", stdin=file)
            compose("exec", "-T", "db", "psql", "-U", "grafana_reader", "-d", database, "-v", "ON_ERROR_STOP=1", "-c",
                    "SELECT name, rating, games, qualified FROM dashboard.standings ORDER BY name")
            print("Restore verified in an isolated temporary database")
        finally:
            compose("exec", "-T", "db", "dropdb", "-U", "postgres", database)
    print(path)


if __name__ == "__main__":
    main()
