import argparse
import logging
import os
import signal
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import psycopg

from collector.api import ChessAPI
from collector.domain import MODES, archive_months, game_record, load_config, recent_months


log = logging.getLogger(__name__)
LOCK_ID = 48201731


def connect():
    return psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)


def initialize(connection, config):
    connection.execute(Path(__file__).with_name("schema.sql").read_text())
    values = (config["name"], config["start"], config["end"], config["timezone"], config["minimum_games"])
    existing = connection.execute(
        "SELECT name, starts_at, ends_at, timezone, minimum_games FROM chess.competition"
    ).fetchone()
    players = {(p["username"], p["name"]) for p in config["players"]}
    if existing and (existing != values or set(connection.execute("SELECT username, name FROM chess.players")) != players):
        raise ValueError("Configuration differs from the stored competition; use a new database for a new competition")
    with connection.transaction():
        connection.execute(
            """INSERT INTO chess.competition (name, starts_at, ends_at, timezone, minimum_games)
               VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""", values
        )
        for username, name in players:
            connection.execute("INSERT INTO chess.players VALUES (%s, %s) ON CONFLICT DO NOTHING", (username, name))


def import_games(connection, games, usernames):
    for game in games:
        record, participants = game_record(game, usernames)
        connection.execute(
            """INSERT INTO chess.games (id, url, ended_at, rated, rules, mode, time_control)
               VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO UPDATE SET
               url = EXCLUDED.url, ended_at = EXCLUDED.ended_at, rated = EXCLUDED.rated,
               rules = EXCLUDED.rules, mode = EXCLUDED.mode, time_control = EXCLUDED.time_control""", record
        )
        for participant in participants:
            connection.execute(
                """INSERT INTO chess.performances
                   (game_id, username, colour, rating, opponent, opponent_rating, result, outcome, accuracy)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (game_id, username) DO UPDATE SET
                   colour = EXCLUDED.colour, rating = EXCLUDED.rating, opponent = EXCLUDED.opponent,
                   opponent_rating = EXCLUDED.opponent_rating, result = EXCLUDED.result,
                   outcome = EXCLUDED.outcome, accuracy = COALESCE(EXCLUDED.accuracy, chess.performances.accuracy)""",
                participant,
            )


def sync(connection, config, full=False, api=None, now=None):
    now = now or datetime.now(timezone.utc)
    api = api or ChessAPI(connection, os.environ.get("CHESS_USER_AGENT", "graf-chess/0.1"))
    usernames = {p["username"] for p in config["players"]}
    run_id = connection.execute(
        "INSERT INTO chess.sync_runs (full_refresh) VALUES (%s) RETURNING id", (full,)
    ).fetchone()[0]
    success = True
    for username in sorted(usernames):
        try:
            with connection.transaction():
                base = f"https://api.chess.com/pub/player/{quote(username, safe='')}"
                stats = api.get(f"{base}/stats")
                archives = api.get(f"{base}/games/archives")["archives"]
                available = {url.rsplit("/", 2)[-2] + "/" + url.rsplit("/", 1)[-1] for url in archives}
                cached = {r[0] for r in connection.execute("SELECT url FROM chess.http_cache WHERE url LIKE %s", (f"{base}/games/%",))}
                for month in archive_months(config["start"], now):
                    url = f"{base}/games/{month}"
                    if month in available and (full or month in recent_months(now) or url not in cached):
                        import_games(connection, api.get(url)["games"], usernames)
                for mode in sorted(MODES):
                    last = stats.get(f"chess_{mode}", {}).get("last")
                    if last:
                        connection.execute(
                            """INSERT INTO chess.snapshots (username, mode, rating, last_game_at)
                               VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                            (username, mode, last["rating"], datetime.fromtimestamp(last["date"], timezone.utc)),
                        )
                connection.execute(
                    """INSERT INTO chess.player_sync (username, last_success_at) VALUES (%s, now())
                       ON CONFLICT (username) DO UPDATE SET last_attempt_at = now(), last_success_at = now(), error = NULL""",
                    (username,),
                )
            log.info("Synced %s", username)
        except Exception as error:
            success = False
            log.exception("Sync failed for %s", username)
            connection.execute(
                """INSERT INTO chess.player_sync (username, error) VALUES (%s, %s)
                   ON CONFLICT (username) DO UPDATE SET last_attempt_at = now(), error = EXCLUDED.error""",
                (username, str(error)[:1000]),
            )
    connection.execute(
        "UPDATE chess.sync_runs SET finished_at = now(), success = %s WHERE id = %s", (success, run_id)
    )
    return success


def finalize(connection, now=None):
    now = now or datetime.now(timezone.utc)
    with connection.transaction():
        end, finalized = connection.execute("SELECT ends_at, finalized_at FROM chess.competition FOR UPDATE").fetchone()
        if finalized:
            raise ValueError("Competition is already finalized")
        if now < end + timedelta(hours=24):
            raise ValueError("Wait until 24 hours after the deadline so delayed API data can arrive")
        refreshed = connection.execute(
            """SELECT EXISTS (SELECT 1 FROM chess.sync_runs WHERE full_refresh AND success
               AND started_at >= %s AND finished_at >= %s)""", (end, now - timedelta(hours=1))
        ).fetchone()[0]
        if not refreshed:
            raise ValueError("Finalization requires a successful full refresh within the last hour")
        connection.execute(
            """INSERT INTO chess.final_results
               SELECT username, rating, games, wins, draws, losses, unknown_results,
                      last_game_at, qualified, rank FROM dashboard.live_standings"""
        )
        connection.execute("UPDATE chess.competition SET finalized_at = %s", (now,))


def health(connection):
    return connection.execute(
        "SELECT EXISTS (SELECT 1 FROM chess.sync_runs WHERE finished_at > now() - interval '3 hours')"
    ).fetchone()[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["run", "sync", "finalize", "health", "init"])
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    with connect() as connection:
        if args.command == "health":
            return 0 if health(connection) else 1
        if not connection.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_ID,)).fetchone()[0]:
            log.error("Another collector command is running; try again after the current sync finishes")
            return 1
        config = load_config(os.environ.get("COMPETITION_CONFIG", "competition.json"))
        initialize(connection, config)
        if args.command == "init":
            return 0
        if args.command == "sync":
            return 0 if sync(connection, config, full=args.full) else 1
        if args.command == "finalize":
            if not args.confirm:
                parser.error("Review standings after a full refresh, then use finalize --confirm to freeze them")
            finalize(connection)
            return 0
        stop = threading.Event()
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: stop.set())
        while not stop.is_set():
            try:
                sync(connection, config)
            except psycopg.Error:
                log.exception("Database error; exiting so the container can restart")
                return 1
            connection.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))
            stop.wait(int(os.environ.get("POLL_SECONDS", "3600")))
            if not stop.is_set():
                while not connection.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_ID,)).fetchone()[0]:
                    if stop.wait(5):
                        break
    return 0


if __name__ == "__main__":
    sys.exit(main())
