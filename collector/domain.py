import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


DRAW_RESULTS = {"agreed", "repetition", "stalemate", "insufficient", "50move", "timevsinsufficient"}
LOSS_RESULTS = {"checkmated", "timeout", "resigned", "lose", "abandoned", "kingofthehill", "threecheck", "bughousepartnerlose"}
MODES = {"rapid", "blitz", "bullet", "daily"}


def load_config(path):
    config = json.loads(Path(path).read_text())
    for field in ("start", "end"):
        config[field] = datetime.fromisoformat(config[field])
        if config[field].tzinfo is None:
            raise ValueError(f"{field} must include a timezone offset")
    ZoneInfo(config["timezone"])
    if config["end"] <= config["start"] or config["minimum_games"] < 1:
        raise ValueError("Invalid competition window or minimum_games")
    seen = set()
    for player in config["players"]:
        player["username"] = player["username"].lower().strip()
        if not player["username"] or player["username"] in seen:
            raise ValueError("Player usernames must be nonempty and unique")
        seen.add(player["username"])
    if not seen:
        raise ValueError("At least one player is required")
    return config


def result_outcome(result):
    if result == "win":
        return "win"
    if result in DRAW_RESULTS:
        return "draw"
    if result in LOSS_RESULTS:
        return "loss"
    return "unknown"


def eligible(game, config):
    return (game.get("rated") is True and game.get("rules") == "chess"
            and game.get("time_class") == "rapid"
            and config["start"].timestamp() <= game["end_time"] < config["end"].timestamp())


def game_record(game, usernames):
    if "end_time" not in game or not all(side in game for side in ("white", "black")):
        raise ValueError("Archive contains an incomplete game")
    key = game.get("uuid") or game["url"]
    ended = datetime.fromtimestamp(game["end_time"], timezone.utc)
    participants = []
    for colour, other in (("white", "black"), ("black", "white")):
        player, opponent = game[colour], game[other]
        username = player["username"].lower()
        if username not in usernames:
            continue
        participants.append((
            key, username, colour, player.get("rating"), opponent["username"].lower(),
            opponent.get("rating"), player["result"], result_outcome(player["result"]),
            (game.get("accuracies") or {}).get(colour),
        ))
    return (key, game["url"], ended, game.get("rated", False), game["rules"],
            game["time_class"], str(game["time_control"])), participants


def archive_months(start, now):
    year, month = start.astimezone(timezone.utc).year, start.astimezone(timezone.utc).month
    last = (now.year, now.month)
    while (year, month) <= last:
        yield f"{year:04d}/{month:02d}"
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


def recent_months(now):
    previous = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
    return {f"{now.year:04d}/{now.month:02d}", f"{previous[0]:04d}/{previous[1]:02d}"}
