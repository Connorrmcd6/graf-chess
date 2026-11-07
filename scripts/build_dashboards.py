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


def dashboard(uid, title, panels, variables=None, tags=("chess-club",)):
    panels.sort(key=lambda item: (item["gridPos"]["y"], item["gridPos"]["x"]))
    for number, item in enumerate(walk_panels(panels), 1):
        item["id"] = number
    return {
        "uid": uid, "title": title, "schemaVersion": 39, "version": 1,
        "editable": False, "timezone": CONFIG["timezone"], "refresh": "5m",
        "tags": list(tags),
        "time": {"from": datetime.fromisoformat(CONFIG["start"]).astimezone(timezone.utc).isoformat().replace("+00:00", "Z"), "to": "now"},
        "timepicker": {}, "annotations": {"list": []}, "panels": panels,
        "templating": {"list": variables or []},
        "links": [{"title": "Player comparison", "url": "/d/chess-players", "type": "link"},
                  {"title": "Recurring mistakes", "url": "/d/chess-mistakes", "type": "link"}],
    }


def recent_games(title, where, x, y, w=24, h=10, description=""):
    return panel(title, f"""SELECT ended_at AS \"Completed\", name AS \"Player\", mode AS \"Mode\", colour AS \"Colour\",
          opponent AS \"Opponent\", outcome AS \"Result\", rating AS \"Rating\", opening AS \"Opening\",
          stockfish_accuracy AS \"Accuracy\", chesscom_accuracy AS \"Chess.com accuracy\",
          blunders AS \"Blunders\", mistakes AS \"Mistakes\", url AS \"Game\"
          FROM dashboard.recent_games WHERE {where} ORDER BY ended_at DESC LIMIT 50""", x, y, w, h,
          description=description or "Accuracy is worked out from our Stockfish analysis (Lichess's formula) and "
                                     "appears once a game is analysed. Chess.com accuracy appears only when someone ran Game Review. "
                                     "The two use different formulas, so compare like with like.")


COMPETITION_FILTER = """g.rated AND g.rules = 'chess' AND g.mode = 'rapid'
AND g.ended_at >= c.starts_at AND g.ended_at < c.ends_at"""
PLAYER_FILTER = """rated AND rules = 'chess' AND username IN (${player:sqlstring})
AND mode IN (${mode:sqlstring}) AND $__timeFilter(ended_at)"""

# The 12-week competition ended on 31 Oct 2026. Its dashboard is kept, read-only, in the Grafana "Archive" folder.
competition = dashboard("chess-competition", "Chess Club | Race to the top (archived)", [
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
], tags=("chess-club", "archived"))

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
    panel("Ratings and opponents", f"""SELECT r.name AS \"Player\", r.mode AS \"Mode\", r.rating AS \"Current rating\",
          s.games AS \"Games\", s.opponent AS \"Avg opponent rating\", r.last_game_at AS \"Last rated game\"
          FROM dashboard.current_ratings r LEFT JOIN (
              SELECT username, mode, count(*) AS games, round(avg(opponent_rating)) AS opponent
              FROM dashboard.games WHERE {PLAYER_FILTER} GROUP BY username, mode) s USING (username, mode)
          WHERE r.username IN (${{player:sqlstring}}) AND r.mode IN (${{mode:sqlstring}})
          ORDER BY r.mode, r.rating DESC""", 0, 13, 12, 10,
          description="Current rating is the latest Chess.com /stats value, whatever the date range. Games and average opponent rating (as recorded after each game) cover the selected date range."),
    bars("Results in selected period", f"""SELECT name || ' / ' || mode AS \"Player / mode\",
          count(*) FILTER (WHERE outcome = 'win') AS \"Wins\",
          count(*) FILTER (WHERE outcome = 'draw') AS \"Draws\",
          count(*) FILTER (WHERE outcome = 'loss') AS \"Losses\",
          count(*) FILTER (WHERE outcome = 'unknown') AS \"Unknown\"
          FROM dashboard.games WHERE {PLAYER_FILTER} GROUP BY name, mode ORDER BY name, mode""", 12, 13, 12, 10, stacked=True),
    panel("Games per day (SAST)", f"""SELECT date_trunc('day', ended_at AT TIME ZONE 'Africa/Johannesburg')
          AT TIME ZONE 'Africa/Johannesburg' AS time, count(*) AS value, name || ' / ' || mode AS metric
          FROM dashboard.games WHERE {PLAYER_FILTER} GROUP BY 1, 3 ORDER BY time""", 0, 23, 12, 9, "timeseries"),
    bars("Average accuracy", f"""SELECT name || ' / ' || mode || ' (' || count(stockfish_accuracy) || ' analysed, '
          || count(chesscom_accuracy) || ' reviewed / ' || count(*) || ')' AS \"Player / coverage\",
          avg(stockfish_accuracy) AS \"Accuracy (Stockfish)\", avg(chesscom_accuracy) AS \"Chess.com accuracy\"
          FROM dashboard.recent_games WHERE {PLAYER_FILTER} GROUP BY name, mode ORDER BY name, mode""", 12, 23, unit="percent",
          description="Stockfish accuracy covers every analysed game; Chess.com's only games put through Game Review. "
                      "The formulas differ, so compare players within one colour of bar, not across them."),
    bars("Club head-to-head", f"""SELECT name || ' vs ' || opponent || ' / ' || mode AS \"Matchup\",
          count(*) FILTER (WHERE outcome = 'win') AS \"Wins\",
          count(*) FILTER (WHERE outcome = 'draw') AS \"Draws\",
          count(*) FILTER (WHERE outcome = 'loss') AS \"Losses\",
          count(*) FILTER (WHERE outcome = 'unknown') AS \"Unknown\"
          FROM dashboard.games WHERE {PLAYER_FILTER}
          AND opponent IN (SELECT username FROM dashboard.players)
          GROUP BY name, opponent, mode ORDER BY name, opponent, mode""", 0, 32, 24, 10, stacked=True,
          description="Each matchup is shown from each selected player's perspective. Do not sum mirrored rows."),
    panel("Accuracy trend (10-game average)", f"""SELECT ended_at AS time, avg(stockfish_accuracy) OVER (
          PARTITION BY username, mode ORDER BY ended_at ROWS 9 PRECEDING) AS value, name || ' / ' || mode AS metric
          FROM dashboard.recent_games WHERE {PLAYER_FILTER} AND stockfish_accuracy IS NOT NULL ORDER BY time""",
          0, 42, 24, 9, "timeseries", "percent",
          description="Average Stockfish accuracy over each player's last 10 analysed games in that mode."),
    recent_games("Recent games", PLAYER_FILTER, 0, 51),
    detail_row([
      panel("Rating timestamps", """SELECT name AS \"Player\", mode AS \"Mode\", rating AS \"Current rating\",
          last_game_at AS \"Last rated game\", observed_at AS \"Fetched\" FROM dashboard.current_ratings
          WHERE username IN (${player:sqlstring}) AND mode IN (${mode:sqlstring}) ORDER BY mode, rating DESC""", 0, 0),
      panel("Accuracy coverage", f"""SELECT name AS \"Player\", mode AS \"Mode\", count(*) AS \"Total games\",
          count(stockfish_accuracy) AS \"Analysed\", round(avg(stockfish_accuracy)::numeric, 1) AS \"Avg accuracy %\",
          count(chesscom_accuracy) AS \"Reviewed on Chess.com\", round(avg(chesscom_accuracy)::numeric, 1) AS \"Avg Chess.com %\",
          count(*) FILTER (WHERE stockfish_accuracy IS NOT NULL AND chesscom_accuracy IS NOT NULL) AS \"Both\",
          round(avg(chesscom_accuracy - stockfish_accuracy)::numeric, 1) AS \"Chess.com minus ours\"
          FROM dashboard.recent_games WHERE {PLAYER_FILTER} GROUP BY name, mode ORDER BY name, mode""", 0, 0,
          description="'Chess.com minus ours' averages the gap over games that have both, to show how the two scales compare."),
      panel("Results by colour", f"""SELECT name AS \"Player\", mode AS \"Mode\", colour AS \"Colour\",
          count(*) AS \"Games\", round(100.0 * count(*) FILTER (WHERE outcome = 'win') / count(*), 1) AS \"Win %\"
          FROM dashboard.games WHERE {PLAYER_FILTER} GROUP BY name, mode, colour ORDER BY name, mode, colour""", 0, 0),
      panel("Collection status", "SELECT name, status, last_success_at FROM dashboard.sync_status ORDER BY name", 0, 0),
    ], 61),
], [player_variable, mode_variable])

MOVE_FILTER = """rated AND username IN (${player:sqlstring}) AND mode IN (${mode:sqlstring}) AND $__timeFilter(ended_at)"""
MOVE_LABEL = "move_number || CASE WHEN colour = 'white' THEN '. ' ELSE '... ' END"
POSITION_LINK = "'https://lichess.org/analysis/' || replace(fen, ' ', '_') || '?color=' || colour"
CLOCK_ORDER = "array_position(ARRAY['3min+', '1-3min', '30-60s', '10-30s', '0-10s'], clock_bucket)"
# One player at a time, chosen explicitly: the placeholder value matches no username, so panels stay empty until then.
single_player_variable = {
    "name": "player", "label": "Player", "type": "query", "datasource": SOURCE,
    "query": """SELECT __text, __value FROM (SELECT 0 AS sort, 'Choose a player' AS __text, '-' AS __value
             UNION ALL SELECT 1, name, username FROM dashboard.players) p ORDER BY sort, __text""",
    "refresh": 1, "multi": False, "includeAll": False,
    "current": {"text": "Choose a player", "value": "-"}, "options": [],
}
mistakes = dashboard("chess-mistakes", "Chess Club | Recurring mistakes", [
    text_panel("Do you keep making the same mistakes?",
               "**Choose a player at the top to begin.** Stockfish checks every move of each game from the last 30 days. A move is an **error** when it drops your winning chances by "
               "10+ points (inaccuracy), 20+ (mistake) or 30+ (blunder). **Positional** errors lose ground without losing "
               "material; **tactical** ones allow or miss a combination. The three tables at the top cover all analysed "
               "games, whatever the date range or mode; the charts below follow the filters. "
               "**Position** opens the position on Lichess.", 0),
    panel("Last 30 days analysed", """SELECT sum(analysed_last_30_days) || ' / ' || sum(games_last_30_days) AS analysed
          FROM dashboard.analysis_status WHERE username IN (${player:sqlstring})""", 0, 3, 6, 3, "stat",
          description="Standard games from the last 30 days for the selected players. Older games are only analysed "
                      "if ANALYSIS_DAYS is raised; games analysed earlier stay on the dashboard."),
    panel("Errors per 100 moves", f"""SELECT round(100.0 * count(*) FILTER (WHERE is_error) / nullif(count(*), 0), 1) AS errors
          FROM dashboard.player_moves WHERE {MOVE_FILTER}""", 12, 3, 6, 3, "stat"),
    panel("Average accuracy", f"""SELECT avg(stockfish_accuracy) AS accuracy FROM dashboard.recent_games
          WHERE {MOVE_FILTER} AND rules = 'chess'""", 6, 3, 6, 3, "stat", "percent",
          description="Stockfish accuracy (Lichess's formula) over analysed games matching the filters."),
    panel("Errors that are positional", f"""SELECT 100.0 * count(*) FILTER (WHERE kind = 'positional') / nullif(count(*), 0) AS positional
          FROM dashboard.errors WHERE {MOVE_FILTER}""", 18, 3, 6, 3, "stat", unit="percent"),
    panel("Same position, same mistake", f"""SELECT name AS \"Player\", opening AS \"Opening\",
          {MOVE_LABEL} || your_move AS \"You play\", engine_move AS \"Engine prefers\",
          times_played AS \"Times\", avg_win_loss AS \"Avg drop\", usual_kind AS \"Type\",
          {POSITION_LINK} AS \"Position\", latest_game AS \"Game\"
          FROM dashboard.repeated_mistakes WHERE username IN (${{player:sqlstring}})
          ORDER BY times_played * avg_win_loss DESC LIMIT 50""", 0, 6, 24, 10,
          description="The same bad move in the same exact position, in two or more games. Avg drop is in winning-chance points."),
    panel("Positions you keep reaching and misplaying", f"""SELECT name AS \"Player\", opening AS \"Opening\",
          {MOVE_LABEL} || usual_move AS \"Usual move\", engine_move AS \"Engine prefers\", games AS \"Games\",
          errors AS \"Errors\", error_rate AS \"Error %\", avg_win_loss AS \"Avg drop\", {POSITION_LINK} AS \"Position\"
          FROM dashboard.repeated_positions WHERE username IN (${{player:sqlstring}}) AND errors > 0
          ORDER BY errors DESC, games DESC LIMIT 50""", 0, 16, 24, 9,
          description="Positions reached in 3+ games where at least one move went wrong, including different wrong moves."),
    panel("Pawn structures where you go wrong", """SELECT name AS \"Player\", colour AS \"Colour\", structure AS \"Structure\",
          games AS \"Games\", errors AS \"Errors\", positional_errors AS \"Positional\", tactical_errors AS \"Tactical\",
          error_rate AS \"Error %\", opening AS \"Opening\", worst_game AS \"Game\"
          FROM dashboard.structure_mistakes WHERE username IN (${player:sqlstring}) AND errors > 0
          ORDER BY errors DESC LIMIT 50""", 0, 25, 24, 9,
          description="After move 10. Same pawns on both sides and kings on the same wings, in 3+ games. Game links the worst error."),
    bars("Error types", f"""SELECT name AS \"Player\",
          count(*) FILTER (WHERE kind = 'positional') AS \"Positional\",
          count(*) FILTER (WHERE kind = 'allowed_tactic') AS \"Allowed a tactic\",
          count(*) FILTER (WHERE kind = 'missed_tactic') AS \"Missed a tactic\"
          FROM dashboard.errors WHERE {MOVE_FILTER} GROUP BY name ORDER BY name""", 0, 34, stacked=True),
    bars("Errors per 100 moves by clock", f"""SELECT name || ' / ' || clock_bucket || ' left' AS \"Player / clock\",
          round(100.0 * count(*) FILTER (WHERE is_error) / count(*), 1) AS \"Errors per 100 moves\"
          FROM dashboard.player_moves WHERE {MOVE_FILTER} AND clock_bucket IS NOT NULL
          GROUP BY name, clock_bucket ORDER BY name, min({CLOCK_ORDER})""", 12, 34,
          description="Time left on your clock after the move."),
    bars("Errors per 100 moves by phase", f"""SELECT name || ' / ' || phase AS \"Player / phase\",
          round(100.0 * count(*) FILTER (WHERE is_error) / count(*), 1) AS \"Errors per 100 moves\",
          round(100.0 * count(*) FILTER (WHERE kind = 'positional') / count(*), 1) AS \"Positional\"
          FROM dashboard.player_moves WHERE {MOVE_FILTER}
          GROUP BY name, phase ORDER BY name, min(array_position(ARRAY['opening', 'middlegame', 'endgame'], phase))""", 0, 43),
    bars("Worst openings (5+ games)", f"""SELECT name || ' / ' || opening AS \"Player / opening\",
          round(count(*) FILTER (WHERE is_error)::numeric / count(DISTINCT game_id), 1) AS \"Errors per game\"
          FROM dashboard.player_moves WHERE {MOVE_FILTER} AND opening IS NOT NULL
          GROUP BY name, opening HAVING count(DISTINCT game_id) >= 5
          ORDER BY 2 DESC LIMIT 15""", 12, 43, description="Chess.com's opening name for each game."),
    recent_games("Recent games", MOVE_FILTER + " AND rules = 'chess'", 0, 52),
], [single_player_variable, mode_variable])

for name, data in (("competition", competition), ("players", players), ("mistakes", mistakes)):
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
            for field in ("Win %", "Avg accuracy %", "Avg Chess.com %", "Accuracy", "Chess.com accuracy"):
                item["fieldConfig"]["overrides"].append({
                    "matcher": {"id": "byName", "options": field},
                    "properties": [{"id": "unit", "value": "percent"}, {"id": "decimals", "value": 1}],
                })
            for field, title in (("Game", "Open game"), ("Position", "Open position on Lichess")):
                item["fieldConfig"]["overrides"].append({
                    "matcher": {"id": "byName", "options": field},
                    "properties": [{"id": "links", "value": [{"title": title, "url": "${__value.raw}", "targetBlank": True}]}],
                })
            if name == "mistakes":
                item["fieldConfig"]["overrides"] += [
                    {"matcher": {"id": "byName", "options": "Error %"},
                     "properties": [{"id": "unit", "value": "percent"}, {"id": "decimals", "value": 1}]},
                    {"matcher": {"id": "byName", "options": "Avg drop"}, "properties": [{"id": "decimals", "value": 1}]}]
    path = ROOT / "grafana" / ("archive" if name == "competition" else "dashboards") / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
print("Generated player comparison and recurring mistakes dashboards, and the archived competition dashboard")
