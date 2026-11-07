import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]


def walk_panels(panels):
    for panel in panels:
        yield panel
        yield from walk_panels(panel.get("panels", []))


def main():
    parser = argparse.ArgumentParser(description="Check provisioned dashboards and every SQL panel through anonymous Grafana access")
    parser.add_argument("--url", default="http://localhost:3000")
    args = parser.parse_args()
    config = json.loads((ROOT / "competition.json").read_text())
    players = ",".join("'" + p["username"].replace("'", "''") + "'" for p in config["players"])
    start = str(int(datetime.fromisoformat(config["start"]).timestamp() * 1000))
    end = str(int(datetime.now(timezone.utc).timestamp() * 1000))
    checks = 0
    for file in sorted([*(ROOT / "grafana/dashboards").glob("*.json"), *(ROOT / "grafana/archive").glob("*.json")]):
        dashboard = json.loads(file.read_text())
        with urlopen(f"{args.url}/api/dashboards/uid/{dashboard['uid']}", timeout=30) as response:
            deployed = json.load(response)
        assert deployed["meta"]["canEdit"] is False, "Anonymous visitor can edit a dashboard"
        for panel in walk_panels(dashboard["panels"]):
            if not panel.get("targets"):
                continue
            for mode in ("rapid", "blitz", "bullet", "daily") if file.stem in ("players", "mistakes") else ("rapid",):
                targets = []
                for target in panel["targets"]:
                    target = dict(target)
                    target["rawSql"] = target["rawSql"].replace("${player:sqlstring}", players).replace("${mode:sqlstring}", f"'{mode}'")
                    targets.append(target)
                body = json.dumps({"from": start, "to": end, "queries": targets}).encode()
                request = Request(f"{args.url}/api/ds/query", data=body, headers={"Content-Type": "application/json"})
                try:
                    with urlopen(request, timeout=30) as response:
                        results = json.load(response)["results"]
                except HTTPError as error:
                    raise RuntimeError(f"{panel['title']} / {mode}: {error.read().decode()}") from error
                for result in results.values():
                    assert not result.get("error"), f"{panel['title']} / {mode}: {result}"
                    assert result.get("status", 200) == 200, result
                checks += 1
        print(f"{dashboard['title']}: panels query successfully; anonymous editing disabled")
    request = Request(f"{args.url}/api/dashboards/db", data=b'{}', headers={"Content-Type": "application/json"})
    try:
        urlopen(request, timeout=30)
    except HTTPError as error:
        assert error.code in (401, 403), f"Unexpected anonymous write response: {error.code}"
    else:
        raise AssertionError("Anonymous dashboard write was not rejected")
    print(f"Passed {checks} panel/mode query checks and anonymous write protection")


if __name__ == "__main__":
    main()
