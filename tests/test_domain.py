import json
from datetime import datetime, timezone

import pytest

from collector.domain import archive_months, eligible, game_record, load_config, recent_months, result_outcome


def test_competition_boundary_and_game_types(config, game):
    start, end = int(config["start"].timestamp()), int(config["end"].timestamp())
    assert not eligible(game(end_time=start - 1), config)
    assert eligible(game(end_time=start), config)
    assert eligible(game(end_time=end - 1), config)
    assert not eligible(game(end_time=end), config)
    for changes in ({"rated": False}, {"rules": "chess960"}, {"time_class": "blitz"}):
        assert not eligible(game(**changes), config)


def test_result_codes_and_missing_accuracy(game):
    assert result_outcome("timevsinsufficient") == "draw"
    assert result_outcome("timeout") == "loss"
    assert result_outcome("unexpected") == "unknown"
    record, participants = game_record(game(username="ALICE", opponent="bob"), {"alice", "bob"})
    assert len(participants) == 2
    assert participants[0][1] == "alice"
    assert participants[0][-1] is None
    assert participants[1][-2] == "loss"


def test_month_rollover_includes_utc_boundary():
    start = datetime.fromisoformat("2026-01-01T00:00:00+02:00")
    now = datetime(2026, 1, 31, tzinfo=timezone.utc)
    assert list(archive_months(start, now)) == ["2025/12", "2026/01"]
    assert recent_months(now) == {"2025/12", "2026/01"}


def test_config_rejects_naive_dates_and_duplicate_usernames(tmp_path):
    value = {"name": "test", "start": "2026-08-08T00:00:00", "end": "2026-10-31T00:00:00+02:00",
             "timezone": "Africa/Johannesburg", "minimum_games": 20,
             "players": [{"username": "Alice", "name": "Alice"}]}
    path = tmp_path / "config.json"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="timezone"):
        load_config(path)
    value["start"] += "+02:00"
    value["players"].append({"username": "alice", "name": "Duplicate"})
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="unique"):
        load_config(path)
