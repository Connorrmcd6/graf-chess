# Chess Club

A Raspberry Pi dashboard for seven friends competing for the highest Chess.com rapid rating over 12 weeks. Python collects public games, PostgreSQL stores them, and Grafana displays the competition and other modes. Python dependencies and commands use **uv**.

Both dashboards lead with rating trends and comparison charts. Rankings, qualification progress, results, win rates, and activity use bars; exact figures, collection timestamps, and game links are available in the collapsed **Details and game links** sections.

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
5. Open **http://localhost:3000** for the competition dashboard; the player-comparison link opens the other dashboard.
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
