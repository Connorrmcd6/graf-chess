import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = {"type": "postgres", "uid": "chess-postgres"}
CONFIG = json.loads((ROOT / "competition.json").read_text())


def panel(title, sql, x, y, w=12, h=8, kind="table", unit="none", description=""):
    return {
        "title": title, "type": kind, "description": description,
        "gridPos": {"x": x, "y": y, "w": w, "h": h}, "datasource": SOURCE,
        "targets": [{"refId": "A", "datasource": SOURCE, "rawSql": sql,
                     "format": "time_series" if kind == "timeseries" else "table", "rawQuery": True}],
        "fieldConfig": {"defaults": {"unit": unit, "decimals": 0,
                                      "color": {"mode": "palette-classic"},
                                      "custom": {"lineWidth": 2, "fillOpacity": 8, "showPoints": "auto", "spanNulls": True,
                                                 "lineInterpolation": "stepAfter", "minWidth": 60}},
                        "overrides": []},
        "options": {"showHeader": True, "cellHeight": "sm", "tooltip": {"mode": "multi", "sort": "desc"},
                    "legend": {"displayMode": "list", "placement": "bottom", "calcs": []},
                    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "/.*/", "values": False},
                    "colorMode": "value", "graphMode": "none", "textMode": "auto"},
    }


def text_panel(title, content, y, h=3):
    return {"title": title, "type": "text", "gridPos": {"x": 0, "y": y, "w": 24, "h": h},
            "options": {"mode": "markdown", "content": content}}


def bars(title, sql, x, y, w=12, h=9, stacked=False, unit="none", description=""):
    item = panel(title, sql, x, y, w, h, "barchart", unit, description)
    item["options"].update({"orientation": "horizontal", "showValue": "never" if stacked else "always", "barWidth": 0.8,
                            "groupWidth": 0.7, "stacking": "normal" if stacked else "none",
                            "tooltip": {"mode": "multi", "sort": "desc", "hideZeros": True},
                            "legend": {"showLegend": stacked, "displayMode": "list", "placement": "bottom"}})
    item["fieldConfig"]["defaults"].update({"min": 0})
    item["fieldConfig"]["defaults"]["custom"].update({"fillOpacity": 85, "lineWidth": 0, "axisWidth": 150})
    if unit == "percent":
        item["fieldConfig"]["defaults"].update({"max": 100, "decimals": 1})
    for name, colour in {"Wins": "green", "Draws": "blue", "Losses": "red", "Unknown": "orange"}.items():
        item["fieldConfig"]["overrides"].append({
            "matcher": {"id": "byName", "options": name},
            "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": colour}}],
        })
    return item


def detail_row(panels, y):
    for index, item in enumerate(panels):
        item["gridPos"] = {"x": 0, "y": y + 1 + index * 8, "w": 24, "h": 8}
    return {"title": "Details and game links", "type": "row", "collapsed": True,
            "gridPos": {"x": 0, "y": y, "w": 24, "h": 1}, "panels": panels}


def walk_panels(panels):
    for item in panels:
        yield item
        yield from walk_panels(item.get("panels", []))


def dashboard(uid, title, panels, variables=None):
    panels.sort(key=lambda item: (item["gridPos"]["y"], item["gridPos"]["x"]))
    for number, item in enumerate(walk_panels(panels), 1):
        item["id"] = number
    return {
        "uid": uid, "title": title, "schemaVersion": 39, "version": 1,
        "editable": False, "timezone": CONFIG["timezone"], "refresh": "5m",
        "tags": ["chess-club"],
        "time": {"from": datetime.fromisoformat(CONFIG["start"]).astimezone(timezone.utc).isoformat().replace("+00:00", "Z"), "to": "now"},
        "timepicker": {}, "annotations": {"list": []}, "panels": panels,
        "templating": {"list": variables or []},
        "links": [{"title": "Competition", "url": "/d/chess-competition", "type": "link"},
                  {"title": "Player comparison", "url": "/d/chess-players", "type": "link"}],
    }


COMPETITION_FILTER = """g.rated AND g.rules = 'chess' AND g.mode = 'rapid'
AND g.ended_at >= c.starts_at AND g.ended_at < c.ends_at"""
PLAYER_FILTER = """rated AND rules = 'chess' AND username IN (${player:sqlstring})
AND mode IN (${mode:sqlstring}) AND $__timeFilter(ended_at)"""

competition = dashboard("chess-competition", "Chess Club | Race to the top", [
    text_panel("12 weeks. One leaderboard.",
               f"**Highest rapid rating at the deadline wins.** Complete **{CONFIG['minimum_games']} rated rapid games** to qualify. "
               f"{datetime.fromisoformat(CONFIG['start']).strftime('%d %b')} - "
               f"{datetime.fromisoformat(CONFIG['end']).strftime('%d %b %Y, %H:%M')} SAST. Equal ratings share a rank.\n\n"
               "Updates can lag behind Chess.com.", 0, 3),
    panel("Competition status", """SELECT CASE WHEN finalized_at IS NOT NULL THEN 'FINAL'
          WHEN now() >= ends_at THEN 'PROVISIONAL - awaiting review'
          WHEN now() < starts_at THEN 'NOT STARTED' ELSE 'IN PROGRESS' END AS status
          FROM dashboard.competition""", 0, 3, 6, 3, "stat"),
    panel("Days remaining", "SELECT greatest(0, ceil(extract(epoch FROM ends_at - now()) / 86400)) AS days FROM dashboard.competition", 6, 3, 6, 3, "stat"),
    panel("Qualified players", "SELECT count(*) AS qualified FROM dashboard.standings WHERE qualified", 12, 3, 6, 3, "stat"),
    panel("Collection health", """SELECT CASE WHEN bool_and(status = 'OK') THEN 'Up to date'
          ELSE count(*) FILTER (WHERE status <> 'OK')::text || ' need attention' END AS status
          FROM dashboard.sync_status""", 18, 3, 6, 3, "stat",
          description="Fetch health only; Chess.com responses can still be delayed. Per-player timestamps are in Details."),
    panel("Rapid rating journey", f"""SELECT g.ended_at AS time, g.rating AS value, g.name AS metric
          FROM dashboard.games g CROSS JOIN dashboard.competition c
          WHERE {COMPETITION_FILTER} ORDER BY time""", 0, 6, 24, 10, "timeseries",
          description="Post-game ratings from available archives. No starting ratings or missing history are inferred."),
    bars("Prize race - qualified players", """SELECT '#' || rank || ' ' || name AS \"Player\", rating AS \"Rapid rating\"
         FROM dashboard.standings WHERE qualified ORDER BY rank, name""", 0, 16, 14),
    bars("Qualification progress", """SELECT s.name || ' (' || s.games || ' / ' || c.minimum_games || ')' AS \"Player\",
         least(s.games, c.minimum_games) AS \"Games toward qualification\"
         FROM dashboard.standings s CROSS JOIN dashboard.competition c ORDER BY s.games DESC, s.name""", 14, 16, 10,
         description="Bars stop at the qualification threshold; labels show the full competition game count."),
    bars("Competition results", """SELECT name AS \"Player\", wins AS \"Wins\", draws AS \"Draws\",
         losses AS \"Losses\", unknown_results AS \"Unknown\" FROM dashboard.standings ORDER BY name""", 0, 25, stacked=True),
    bars("Competition win rate", """SELECT name || ' (' || games || ' games)' AS \"Player\",
         100.0 * wins / nullif(games, 0) AS \"Win rate\" FROM dashboard.standings
         ORDER BY 100.0 * wins / nullif(games, 0) DESC NULLS LAST, name""", 12, 25, unit="percent"),
    detail_row([
      panel("Exact standings", """SELECT rank AS \"Rank\", name AS \"Player\", rating AS \"Rapid rating\",
          games AS \"Games\", wins AS \"Wins\", draws AS \"Draws\", losses AS \"Losses\",
          round(100.0 * wins / nullif(games, 0), 1) AS \"Win %\", last_game_at AS \"Last game\"
          FROM dashboard.standings ORDER BY rank NULLS LAST, name""", 0, 0),
      panel("Recent competition games", f"""SELECT g.ended_at AS \"Completed\", g.name AS \"Player\",
          g.opponent AS \"Opponent\", g.outcome AS \"Result\", g.rating AS \"Rating\", g.url AS \"Game\"
          FROM dashboard.games g CROSS JOIN dashboard.competition c
          WHERE {COMPETITION_FILTER} ORDER BY g.ended_at DESC LIMIT 30""", 0, 0),
      panel("Collection status", """SELECT name AS \"Player\", status AS \"Status\",
          last_success_at AS \"Last successful collection\", last_attempt_at AS \"Last attempt\"
          FROM dashboard.sync_status ORDER BY name""", 0, 0),
    ], 37),
    text_panel("Historical coverage", "Charts begin with each account's available game history. "
               "A missing archive is not evidence that no games were played. "
               "Only imported competition games count toward qualification. "
               "The original spreadsheet's ratings and game counts are not used for scoring.", 34),
])

player_variable = {
    "name": "player", "label": "Players", "type": "query", "datasource": SOURCE,
    "query": "SELECT name AS __text, username AS __value FROM dashboard.players ORDER BY name",
    "refresh": 1, "multi": True, "includeAll": True,
    "current": {"text": ["All"], "value": ["$__all"]}, "options": [],
}
mode_variable = {
    "name": "mode", "label": "Mode", "type": "custom", "query": "rapid,blitz,bullet,daily",
    "multi": True, "includeAll": True, "current": {"text": ["rapid"], "value": ["rapid"]},
    "options": [{"text": mode, "value": mode, "selected": mode == "rapid"}
                for mode in ("rapid", "blitz", "bullet", "daily")],
}
players = dashboard("chess-players", "Chess Club | Player comparison", [
    text_panel("Explore your games", "Choose players, modes and a date range. Game statistics cover **rated standard chess** "
               "from August 2026 onward. Current account ratings are shown separately and can include games after the competition. "
               "Missing accuracy is excluded from averages; sample counts show coverage.", 0),
    panel("Rating history", f"""SELECT ended_at AS time, rating AS value, name || ' / ' || mode AS metric
          FROM dashboard.games WHERE {PLAYER_FILTER} ORDER BY time""", 0, 3, 24, 10, "timeseries"),
    bars("Current account ratings", """SELECT name || ' / ' || mode AS \"Player / mode\", rating AS \"Current rating\"
          FROM dashboard.current_ratings WHERE username IN (${player:sqlstring}) AND mode IN (${mode:sqlstring})
          ORDER BY mode, rating DESC""", 0, 13, 12, 10,
          description="Latest /stats observation; independent of the dashboard date range and prize leaderboard."),
    bars("Results in selected period", f"""SELECT name || ' / ' || mode AS \"Player / mode\",
          count(*) FILTER (WHERE outcome = 'win') AS \"Wins\",
          count(*) FILTER (WHERE outcome = 'draw') AS \"Draws\",
          count(*) FILTER (WHERE outcome = 'loss') AS \"Losses\",
          count(*) FILTER (WHERE outcome = 'unknown') AS \"Unknown\"
          FROM dashboard.games WHERE {PLAYER_FILTER} GROUP BY name, mode ORDER BY name, mode""", 12, 13, 12, 10, stacked=True),
    panel("Games per day (SAST)", f"""SELECT date_trunc('day', ended_at AT TIME ZONE 'Africa/Johannesburg')
          AT TIME ZONE 'Africa/Johannesburg' AS time, count(*) AS value, name || ' / ' || mode AS metric
          FROM dashboard.games WHERE {PLAYER_FILTER} GROUP BY 1, 3 ORDER BY time""", 0, 23, 12, 9, "timeseries"),
    bars("Win rate by colour", f"""SELECT name || ' / ' || mode AS \"Player / mode\",
          100.0 * count(*) FILTER (WHERE colour = 'white' AND outcome = 'win') /
              nullif(count(*) FILTER (WHERE colour = 'white'), 0) AS \"White\",
          100.0 * count(*) FILTER (WHERE colour = 'black' AND outcome = 'win') /
              nullif(count(*) FILTER (WHERE colour = 'black'), 0) AS \"Black\"
          FROM dashboard.games WHERE {PLAYER_FILTER} GROUP BY name, mode ORDER BY name, mode""", 12, 23, unit="percent",
          description="Wins divided by all games played with that colour. No games produces a missing value, not zero."),
    bars("Average opponent rating", f"""SELECT name || ' / ' || mode AS \"Player / mode\",
          avg(opponent_rating) AS \"Opponent rating\"
          FROM dashboard.games WHERE {PLAYER_FILTER} GROUP BY name, mode ORDER BY name, mode""", 0, 32,
          description="Opponent ratings as recorded after each game."),
    bars("Average accuracy", f"""SELECT name || ' / ' || mode || ' (' || count(accuracy) || '/' || count(*) || ')' AS \"Player / coverage\",
          avg(accuracy) AS \"Accuracy\"
          FROM dashboard.games WHERE {PLAYER_FILTER} GROUP BY name, mode ORDER BY name, mode""", 12, 32, unit="percent",
          description="Labels show games with accuracy / total games. Missing accuracy is excluded from averages."),
    bars("Club head-to-head", f"""SELECT name || ' vs ' || opponent || ' / ' || mode AS \"Matchup\",
          count(*) FILTER (WHERE outcome = 'win') AS \"Wins\",
          count(*) FILTER (WHERE outcome = 'draw') AS \"Draws\",
          count(*) FILTER (WHERE outcome = 'loss') AS \"Losses\",
          count(*) FILTER (WHERE outcome = 'unknown') AS \"Unknown\"
          FROM dashboard.games WHERE {PLAYER_FILTER}
          AND opponent IN (SELECT username FROM dashboard.players)
          GROUP BY name, opponent, mode ORDER BY name, opponent, mode""", 0, 41, 24, 10, stacked=True,
          description="Each matchup is shown from each selected player's perspective. Do not sum mirrored rows."),
    detail_row([
      panel("Rating timestamps", """SELECT name AS \"Player\", mode AS \"Mode\", rating AS \"Current rating\",
          last_game_at AS \"Last rated game\", observed_at AS \"Fetched\" FROM dashboard.current_ratings
          WHERE username IN (${player:sqlstring}) AND mode IN (${mode:sqlstring}) ORDER BY mode, rating DESC""", 0, 0),
      panel("Accuracy coverage", f"""SELECT name AS \"Player\", mode AS \"Mode\",
          round(avg(accuracy)::numeric, 1) AS \"Avg accuracy %\",
          count(accuracy) AS \"Games with accuracy\", count(*) AS \"Total games\"
          FROM dashboard.games WHERE {PLAYER_FILTER} GROUP BY name, mode ORDER BY name, mode""", 0, 0),
      panel("Results by colour", f"""SELECT name AS \"Player\", mode AS \"Mode\", colour AS \"Colour\",
          count(*) AS \"Games\", round(100.0 * count(*) FILTER (WHERE outcome = 'win') / count(*), 1) AS \"Win %\"
          FROM dashboard.games WHERE {PLAYER_FILTER} GROUP BY name, mode, colour ORDER BY name, mode, colour""", 0, 0),
      panel("Collection status", "SELECT name, status, last_success_at FROM dashboard.sync_status ORDER BY name", 0, 0),
    ], 51),
], [player_variable, mode_variable])

for name, data in (("competition", competition), ("players", players)):
    for item in walk_panels(data["panels"]):
        if item["title"] == "Qualification progress":
            item["fieldConfig"]["defaults"].update({"max": CONFIG["minimum_games"], "color": {"mode": "thresholds"},
                "thresholds": {"mode": "absolute", "steps": [{"color": "orange", "value": None},
                              {"color": "green", "value": CONFIG["minimum_games"]}]}})
        if item["title"] == "Games per day (SAST)":
            item["fieldConfig"]["defaults"]["custom"].update({"drawStyle": "bars", "fillOpacity": 80,
                "lineWidth": 0, "spanNulls": False, "stacking": {"mode": "normal", "group": "games"}})
        if item["title"] == "Win rate by colour":
            item["options"]["legend"]["showLegend"] = True
            for field, colour in (("White", "#EEEEEE"), ("Black", "#5794F2")):
                item["fieldConfig"]["overrides"].append({"matcher": {"id": "byName", "options": field},
                    "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": colour}}]})
        if item["type"] == "table":
            for field, width in {"Rank": 60, "Player": 110, "Rapid rating": 100, "Current rating": 110,
                                 "Mode": 75, "Games": 70, "Wins": 60, "Draws": 60, "Losses": 65,
                                 "Unknown": 85, "Win %": 75, "Last game": 165}.items():
                item["fieldConfig"]["overrides"].append({
                    "matcher": {"id": "byName", "options": field},
                    "properties": [{"id": "custom.width", "value": width}],
                })
            for field in ("Win %", "Avg accuracy %"):
                item["fieldConfig"]["overrides"].append({
                    "matcher": {"id": "byName", "options": field},
                    "properties": [{"id": "unit", "value": "percent"}, {"id": "decimals", "value": 1}],
                })
            item["fieldConfig"]["overrides"].append({
                "matcher": {"id": "byName", "options": "Game"},
                "properties": [{"id": "links", "value": [{"title": "Open game", "url": "${__value.raw}", "targetBlank": True}]}],
            })
    path = ROOT / "grafana" / "dashboards" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
print("Generated competition and player comparison dashboards")
