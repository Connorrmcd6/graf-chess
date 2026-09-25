CREATE SCHEMA IF NOT EXISTS chess;
CREATE SCHEMA IF NOT EXISTS dashboard;

CREATE TABLE IF NOT EXISTS chess.competition (
    id boolean PRIMARY KEY DEFAULT true CHECK (id),
    name text NOT NULL,
    starts_at timestamptz NOT NULL,
    ends_at timestamptz NOT NULL,
    timezone text NOT NULL,
    minimum_games integer NOT NULL CHECK (minimum_games > 0),
    finalized_at timestamptz,
    CHECK (ends_at > starts_at)
);
CREATE TABLE IF NOT EXISTS chess.players (
    username text PRIMARY KEY,
    name text NOT NULL
);
CREATE TABLE IF NOT EXISTS chess.games (
    id text PRIMARY KEY,
    url text NOT NULL UNIQUE,
    ended_at timestamptz NOT NULL,
    rated boolean NOT NULL,
    rules text NOT NULL,
    mode text NOT NULL,
    time_control text NOT NULL
);
CREATE INDEX IF NOT EXISTS games_ended_idx ON chess.games (ended_at);
CREATE TABLE IF NOT EXISTS chess.performances (
    game_id text REFERENCES chess.games(id) ON DELETE CASCADE,
    username text REFERENCES chess.players(username),
    colour text NOT NULL,
    rating integer,
    opponent text NOT NULL,
    opponent_rating integer,
    result text NOT NULL,
    outcome text NOT NULL,
    accuracy double precision,
    PRIMARY KEY (game_id, username)
);
CREATE INDEX IF NOT EXISTS performances_player_idx ON chess.performances(username);
CREATE TABLE IF NOT EXISTS chess.snapshots (
    username text REFERENCES chess.players(username),
    observed_at timestamptz NOT NULL DEFAULT now(),
    mode text NOT NULL,
    rating integer NOT NULL,
    last_game_at timestamptz NOT NULL,
    PRIMARY KEY (username, observed_at, mode)
);
CREATE TABLE IF NOT EXISTS chess.http_cache (
    url text PRIMARY KEY,
    etag text,
    modified text,
    payload jsonb NOT NULL,
    checked_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS chess.sync_runs (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    full_refresh boolean NOT NULL,
    success boolean NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS chess.player_sync (
    username text PRIMARY KEY REFERENCES chess.players(username),
    last_attempt_at timestamptz NOT NULL DEFAULT now(),
    last_success_at timestamptz,
    error text
);
CREATE TABLE IF NOT EXISTS chess.final_results (
    username text PRIMARY KEY REFERENCES chess.players(username),
    rating integer,
    games bigint NOT NULL,
    wins bigint NOT NULL,
    draws bigint NOT NULL,
    losses bigint NOT NULL,
    unknown_results bigint NOT NULL,
    last_game_at timestamptz,
    qualified boolean NOT NULL,
    rank bigint
);

CREATE OR REPLACE VIEW dashboard.games AS
SELECT g.*, p.username, u.name, p.colour, p.rating, p.opponent, p.opponent_rating,
       p.result, p.outcome, p.accuracy
FROM chess.games g JOIN chess.performances p ON p.game_id = g.id
JOIN chess.players u ON u.username = p.username;

CREATE OR REPLACE VIEW dashboard.live_standings AS
WITH eligible AS (
    SELECT g.* FROM dashboard.games g CROSS JOIN chess.competition c
    WHERE g.rated AND g.rules = 'chess' AND g.mode = 'rapid'
      AND g.ended_at >= c.starts_at AND g.ended_at < c.ends_at
), counts AS (
    SELECT username, count(*) AS games,
           count(*) FILTER (WHERE outcome = 'win') AS wins,
           count(*) FILTER (WHERE outcome = 'draw') AS draws,
           count(*) FILTER (WHERE outcome = 'loss') AS losses,
           count(*) FILTER (WHERE outcome = 'unknown') AS unknown_results
    FROM eligible GROUP BY username
), latest AS (
    SELECT DISTINCT ON (username) username, rating, ended_at
    FROM eligible ORDER BY username, ended_at DESC, id DESC
), standings AS (
    SELECT u.username, u.name, l.rating, COALESCE(n.games, 0) AS games,
           COALESCE(n.wins, 0) AS wins, COALESCE(n.draws, 0) AS draws,
           COALESCE(n.losses, 0) AS losses, COALESCE(n.unknown_results, 0) AS unknown_results,
           l.ended_at AS last_game_at,
           COALESCE(n.games >= c.minimum_games AND l.rating IS NOT NULL, false) AS qualified
    FROM chess.players u CROSS JOIN chess.competition c
    LEFT JOIN counts n USING (username) LEFT JOIN latest l USING (username)
)
SELECT *, CASE WHEN qualified THEN rank() OVER (PARTITION BY qualified ORDER BY rating DESC NULLS LAST) END AS rank
FROM standings;

CREATE OR REPLACE VIEW dashboard.standings AS
SELECT s.* FROM dashboard.live_standings s CROSS JOIN chess.competition c WHERE c.finalized_at IS NULL
UNION ALL
SELECT f.username, p.name, f.rating, f.games, f.wins, f.draws, f.losses, f.unknown_results,
       f.last_game_at, f.qualified, f.rank
FROM chess.final_results f JOIN chess.players p USING (username)
CROSS JOIN chess.competition c WHERE c.finalized_at IS NOT NULL;

CREATE OR REPLACE VIEW dashboard.competition AS SELECT * FROM chess.competition;
CREATE OR REPLACE VIEW dashboard.players AS SELECT * FROM chess.players;
CREATE OR REPLACE VIEW dashboard.sync_status AS
SELECT p.username, p.name, s.last_attempt_at, s.last_success_at,
       CASE WHEN s.error IS NOT NULL THEN 'Error - see collector logs'
            WHEN s.last_success_at IS NULL THEN 'Awaiting first import'
            WHEN s.last_success_at < now() - interval '3 hours' THEN 'Stale'
            ELSE 'OK' END AS status
FROM chess.players p LEFT JOIN chess.player_sync s USING (username);
CREATE OR REPLACE VIEW dashboard.current_ratings AS
SELECT DISTINCT ON (s.username, s.mode) s.username, p.name, s.mode, s.rating,
       s.observed_at, s.last_game_at
FROM chess.snapshots s JOIN chess.players p USING (username)
ORDER BY s.username, s.mode, s.observed_at DESC;

GRANT USAGE ON SCHEMA dashboard TO grafana_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA dashboard TO grafana_reader;
