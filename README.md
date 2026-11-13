# Chess Club

A Raspberry Pi dashboard for seven friends competing for the highest Chess.com rapid rating over 12 weeks. Python collects public games, PostgreSQL stores them, and Grafana displays the competition and other modes. Python dependencies and commands use **uv**.

The 12-week competition ended on 31 October 2026. Its dashboard is now in Grafana's **Archive** folder, still readable but no longer the home page or in the dashboard links. The home page is **Player comparison**, alongside **Recurring mistakes** (engine analysis, below). The dashboards lead with rating trends and comparison charts. Rankings, qualification progress, results, win rates, and activity use bars; exact figures, collection timestamps, and game links are available in the collapsed **Details and game links** sections.

## Competition

- Start: **8 August 2026, 00:00 SAST** (7 August, 22:00 UTC), inclusive.
- Deadline: **31 October 2026, 00:00 SAST** (30 October, 22:00 UTC), exclusive.
- Qualification: at least **20 rated standard rapid games completed within that window**.
- Score: the rating recorded after the player's last eligible game, not their peak or rating gain. Equal ratings share a rank.
- Unqualified players remain visible. No starting rating is required.

Players are configured in [competition.json](competition.json). The original spreadsheet was used to identify participants; its weekly ratings and inconsistent game totals are not imported. Connor's currently available archives start August 30, so earlier activity cannot be reconstructed from that account. Missing history is not filled in or counted toward qualification.

The [Published Data API](https://www.chess.com/news/view/published-data-api) can serve delayed responses. Collection runs hourly, using serial requests, conditional caching, and retry backoff. Grafana refreshes every five minutes, but this does not make Chess.com's source data live. The collection-status panel shows fetch health, separately from each player's last game timestamp.

## Start locally or on the Pi

Use a Pi 5 with a **64-bit OS**, Docker Engine with Compose v2, and [uv](https://docs.astral.sh/uv/getting-started/installation/). The same stack runs on an ARM64 Mac. Keep the Pi powered on with reliable storage and internet access.

1. `uv sync --locked` installs the locked Python environment.
2. `uv run scripts/setup.py` generates `.env` with random credentials and restrictive permissions; it never overwrites an existing file.
3. Edit `.env` to set `CHESS_USER_AGENT` to an identifiable value with contact information, for example `graf-chess/0.1 (contact: you@example.com)`.
4. `docker compose up -d --build` builds the collector and database images and starts all three services.
5. Open **http://localhost:3000** for the player comparison dashboard; the links at the top open Recurring mistakes, and the archived competition is under Dashboards → Archive.
6. `docker compose ps` checks health; `docker compose logs --tail 50 collector` shows import progress and failures.

On macOS, prefix long builds/tests with `caffeinate -i`. On Raspberry Pi OS, run the commands directly. Initial startup waits for the first collection cycle before starting Grafana. A failed API request does not prevent viewing previously imported data. Container health checks that the worker is running collection cycles; the collection-status panel reports per-player errors and freshness. No Chess.com API key is needed.

The Grafana admin username is `admin`; its generated password is in `.env`. Anonymous visitors have Viewer access and cannot edit dashboards. Only the `dashboard` database views are accessible to Grafana's database account. These views contain public chess data for all configured participants.

## Your domain and existing Cloudflare Tunnel

Set `GRAFANA_ROOT_URL=https://chess.your-domain.example` and `GRAFANA_COOKIE_SECURE=true` in `.env`, then recreate Grafana with `docker compose up -d grafana`. Open the HTTPS domain to log in after enabling secure cookies.

- **cloudflared runs on the Pi host:** route the hostname to `http://127.0.0.1:3000` in your existing tunnel configuration.
- **cloudflared runs in Docker:** set `CLOUDFLARE_NETWORK` in `.env` to its existing Docker network, start with `docker compose -f compose.yaml -f compose.tunnel.yaml up -d`, and route the hostname to `http://graf-chess-dashboard:3000`. Use both Compose files for subsequent stack lifecycle commands too.

No router port forwarding is required. Grafana's host port binds only to loopback; PostgreSQL has no published port. This project does not create or modify your Cloudflare account, tunnel, DNS, or existing services. Keep this Grafana instance dedicated to the public chess dashboards.

## Data and operation

The initial import fetches all available monthly archives overlapping the competition start through the present. Routine sync revisits the current and previous UTC month and any month not previously fetched. Full refresh revisits all months since the start. Other-mode statistics use rated standard chess and the selected date range; current account ratings come from `/stats` and ignore that date range.

Game results, colour, opponent post-game ratings, accuracy coverage, head-to-head results, and game links are available in the player dashboard. Missing accuracy remains null. The same game appearing in two friends' archives is stored once, with a separate result for each player. Failed player imports roll back together and leave previous data intact; other players still sync.

Competition settings and participant identities are checked against the database on startup. Changing the scoring window or player list in an existing database fails explicitly rather than silently changing a running competition. Use a separate Compose project/database for a new competition.

Useful commands:

```sh
docker compose exec collector chess-collector sync
docker compose exec collector chess-collector sync --full
docker compose logs --tail 100 collector
docker compose restart collector
docker compose down
```

One collector command runs at a time. If a manual command reports that a sync is already running, retry after that sync finishes. Volumes persist through `docker compose down`; **do not add `--volumes`** unless you intend to erase the data.

## Final standings

Post-deadline games never affect the competition. After the deadline, standings are labelled provisional until explicitly finalized. Wait at least 24 hours for delayed API data, then:

1. `docker compose exec collector chess-collector sync --full` refreshes all competition archives.
2. Review the prize leaderboard, qualification counts, and collection status.
3. Within one hour of that successful refresh, run `docker compose exec collector chess-collector finalize --confirm` to save the immutable prize standings.

Finalization is refused before the grace period, without a recent successful full refresh, or if already finalized. Later archive corrections can still appear in exploratory charts, but cannot modify the saved prize results. The 24-hour wait is a conservative operational rule, not a guarantee of API completeness.

## Recurring mistakes (engine analysis)

The `analyser` service runs Stockfish over collected standard games from the last 60 days, using the PGNs the collector has already cached; nothing extra is fetched from Chess.com. It works through any backlog, then checks for new games every 30 minutes. The **Recurring mistakes** dashboard shows the results.

- **Same position, same mistake:** each position gets a fingerprint (pieces, side to move, castling, ignoring move counters, so transpositions match). When you play the same bad move from the same position in two or more games, it is listed with the engine's preferred move and a Lichess link to the position.
- **Pawn structures:** after move 10, moves are also grouped by both sides' pawns and which wing each king is on. This shows similar middlegames where you keep going wrong.
- **Positional or tactical:** an error is a move that drops your winning chances by 10+ points (inaccuracy), 20+ (mistake) or 30+ (blunder), using the Lichess formula. It is `allowed_tactic` if the opponent's best reply wins 2+ pawns of material or forces mate, `missed_tactic` if the engine's move would have, and `positional` otherwise.

- **Accuracy:** each analysed game also gets an accuracy for both sides, using Lichess's published formula over the same evaluations, so it needs no extra engine time. It appears next to Chess.com's accuracy in the **Recent games** tables. Chess.com's figure exists only for games put through Game Review, and its formula is private. On sampled games the two differed unpredictably (anything from 18 points lower to 33 higher), so they are shown side by side and never mixed in averages.

Results are stored in `chess.analysed_games` and `chess.move_analysis` and exposed through the `dashboard.player_moves`, `errors`, `repeated_mistakes`, `repeated_positions`, `structure_mistakes` and `analysis_status` views. A game whose PGN can't be analysed is recorded with `status = 'error'` and skipped; delete its `chess.analysed_games` row to retry it. If Stockfish itself crashes, the service exits and Docker restarts it without marking any game as failed.

On a Pi 5 a rapid game takes about 15 seconds at the defaults (depth 14, at most 1 second per position, 2 threads), so the first pass over 60 days of games (about 1,900 for the club) takes 6-7 hours. After that, new games are analysed within the hour. Games analysed earlier stay in the results as they age past the window. Set `ANALYSIS_DAYS` in `.env` to change the window (`0` analyses everything, about 15 seconds per extra game). `ANALYSIS_THREADS` and `ANALYSIS_DEPTH` trade speed against CPU left for PostgreSQL and Grafana. To run a one-off pass yourself, stop the service first; only one analyser can run at a time:

```sh
docker compose stop analyser
docker compose run --rm analyser --all
```

Stockfish judges *that* a move was worse and what was better, not *why* in human terms. Look at the top repeated positions and structures on Lichess, or ask Claude to explain the recurring idea behind them.

## Mistakes app (phone)

The `web` service is a small phone-first app for the engine analysis, in the same style as mealbot. Add it to your home screen from the browser's share menu. It has five tabs:

- **Patterns:** accuracy, error rate and blunders, the bad moves you repeat from the same position, and where errors happen (game phase, clock, openings).
- **Review:** your recent mistakes and blunders, newest first.
- **Drill:** a position you got wrong; find the move, then tap to see what you played and what the engine wanted. Positions you've misplayed more than once come first. The score is kept on the phone only.
- **Openings:** practise the repertoire in `collector/openings.py` line by line. New lines start in Learn mode (each move shown as an arrow), then Practise is from memory. Hidden mode, per opening or across all your White or Black openings, doesn't say which line is coming, so you answer whatever the opponent plays. A line is learned after three clean runs and comes back for review after 2, 4, 8... days. Progress is kept on the phone only.
- **Games:** recent games with our accuracy and Chess.com's, each opening a list of that game's errors.

Every board shows your move as a red arrow and the engine's as a green one, and every position has an **Open in Lichess** button. Boards are drawn by the server or, where you move pieces, in the browser, so the app loads nothing from other sites. It connects as Grafana's read-only database role and can't change anything.

It is public, like the Grafana dashboards, and shows the same public chess data. It listens on loopback port 8083; publish it through the same Cloudflare Tunnel as Grafana by adding a second public hostname (for example `mistakes.your-domain.example`) whose service is `http://127.0.0.1:8083` (or `http://graf-chess-web-1:8083` if cloudflared runs in Docker on the same network). Grafana and the app need separate hostnames because both use paths such as `/api`.

Because it is public, identical API requests are answered from a 60-second in-memory cache, at most four database queries run at once (Grafana's read-only role allows ten connections), and pages send a Content-Security-Policy that blocks scripts, images and frames from other sites. Visitors pick their own player; the choice and the drill score stay on their phone.

## Backups and recovery

```sh
uv run scripts/backup.py --verify
uv run scripts/restore.py backups/chess-TIMESTAMP.dump --confirm
```

Backups include games, API cache, snapshots, competition settings, and finalized standings. Verification restores the backup into a temporary database, queries it using Grafana's read-only role, then removes only that temporary database. Restore replaces the current chess database and stops the collector/Grafana during the operation; if it fails, they remain stopped for inspection.

Copy backups off the Pi regularly. Preserve `.env` securely and keep the project configuration with your backup. Dashboards are provisioned from files; local Grafana preferences live in the separate `grafana-data` volume. On a fresh host, start the database first so its roles exist, then restore before starting the full stack. For a containerized tunnel, apply `compose.tunnel.yaml` again when starting Grafana after a restore.

## Development and tests

GitHub Actions runs the PostgreSQL integration tests, checks that generated dashboards match their source, validates Compose, and builds the collector and database images. CI uses temporary credentials and does not query Chess.com or deploy anything.

```sh
uv sync --locked
uv run pytest
uv run pytest --integration
uv run scripts/build_dashboards.py
uv run scripts/check_dashboards.py
```

The integration suite starts and removes its own disposable PostgreSQL container. It checks qualification, ties, exact time boundaries, excluded game types, latest versus peak rating, missing history, deduplication, delayed accuracy, failures, caching, and finalization. It also proves that the Grafana database role can read dashboard views but cannot read collector internals or modify data.

Edit `scripts/build_dashboards.py` and regenerate the JSON files to change dashboards. Grafana reloads provisioned dashboard files automatically. The collector Docker image uses `uv sync --locked --no-dev`; local work uses `uv run` without activating an environment. Run `uv lock --upgrade` deliberately when updating Python dependencies, and rebuild/test before deployment.

Runtime validation on the actual Pi and connection of the final domain require access to that Pi and your existing tunnel configuration.
