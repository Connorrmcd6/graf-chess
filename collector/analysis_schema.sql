-- Engine analysis of collected games. Applied by `chess-analyse` on startup; safe to re-run.

CREATE TABLE IF NOT EXISTS chess.analysed_games (
    game_id text PRIMARY KEY REFERENCES chess.games(id) ON DELETE CASCADE,
    analysed_at timestamptz NOT NULL DEFAULT now(),
    engine text,
    depth integer,
    status text NOT NULL CHECK (status IN ('ok', 'error')),
    error text,
    eco text,
    opening text,
    plies integer
);
-- Lichess-style accuracy (0-100) worked out from the engine evals; Chess.com's own figure stays in chess.performances.
ALTER TABLE chess.analysed_games ADD COLUMN IF NOT EXISTS white_accuracy double precision;
ALTER TABLE chess.analysed_games ADD COLUMN IF NOT EXISTS black_accuracy double precision;

CREATE TABLE IF NOT EXISTS chess.move_analysis (
    game_id text REFERENCES chess.analysed_games(game_id) ON DELETE CASCADE,
    ply integer NOT NULL,
    move_number integer NOT NULL,
    colour text NOT NULL CHECK (colour IN ('white', 'black')),
    san text NOT NULL,
    uci text NOT NULL,
    fen_before text NOT NULL,
    position_key text NOT NULL,      -- exact position (transpositions match)
    structure_key text NOT NULL,     -- pawns + king wings only
    structure text NOT NULL,         -- readable form of structure_key
    phase text NOT NULL CHECK (phase IN ('opening', 'middlegame', 'endgame')),
    clock_seconds double precision,  -- mover's clock after the move
    time_spent_seconds double precision,
    eval_before integer NOT NULL,    -- centipawns, mover's point of view, clamped +-2000
    eval_after integer NOT NULL,
    best_uci text,
    best_san text,
    best_line text,
    cp_loss integer NOT NULL,
    win_loss double precision NOT NULL,  -- drop in winning chances, percentage points
    classification text NOT NULL
        CHECK (classification IN ('best', 'good', 'inaccuracy', 'mistake', 'blunder')),
    kind text CHECK (kind IN ('allowed_tactic', 'missed_tactic', 'positional')),
    PRIMARY KEY (game_id, ply)
);
CREATE INDEX IF NOT EXISTS move_analysis_position_idx ON chess.move_analysis (position_key);
CREATE INDEX IF NOT EXISTS move_analysis_structure_idx ON chess.move_analysis (structure_key);

-- Every analysed move made by a tracked player, with game context.
CREATE OR REPLACE VIEW dashboard.player_moves AS
SELECT p.username, u.name, g.id AS game_id, g.url, g.ended_at, g.rated, g.mode, g.time_control,
       a.eco, a.opening, p.outcome,
       m.ply, m.move_number, m.colour, m.san, m.fen_before, m.position_key, m.structure_key,
       m.structure, m.phase, m.clock_seconds, m.time_spent_seconds, m.eval_before, m.eval_after,
       m.best_san, m.best_line, m.cp_loss, m.win_loss, m.classification, m.kind,
       m.classification IN ('inaccuracy', 'mistake', 'blunder') AS is_error,
       CASE WHEN m.clock_seconds IS NULL THEN NULL
            WHEN m.clock_seconds < 10 THEN '0-10s'
            WHEN m.clock_seconds < 30 THEN '10-30s'
            WHEN m.clock_seconds < 60 THEN '30-60s'
            WHEN m.clock_seconds < 180 THEN '1-3min'
            ELSE '3min+' END AS clock_bucket,
       m.uci, m.best_uci, m.eval_before AS eval_before_cp
FROM chess.move_analysis m
JOIN chess.analysed_games a ON a.game_id = m.game_id AND a.status = 'ok'
JOIN chess.games g ON g.id = m.game_id
JOIN chess.performances p ON p.game_id = m.game_id AND p.colour = m.colour
JOIN chess.players u ON u.username = p.username;

-- Layer 1: the same bad move played again in the same exact position.
CREATE OR REPLACE VIEW dashboard.repeated_mistakes AS
SELECT username, name, position_key, san AS your_move,
       mode() WITHIN GROUP (ORDER BY best_san) AS engine_move,
       count(DISTINCT game_id) AS times_played,
       round(avg(win_loss)::numeric, 1) AS avg_win_loss,
       round(avg(cp_loss)::numeric) AS avg_cp_loss,
       mode() WITHIN GROUP (ORDER BY kind) AS usual_kind,
       mode() WITHIN GROUP (ORDER BY opening) AS opening,
       min(move_number) AS move_number,
       min(colour) AS colour,
       min(fen_before) AS fen,
       (array_agg(url ORDER BY ended_at DESC))[1] AS latest_game
FROM dashboard.player_moves
WHERE is_error
GROUP BY username, name, position_key, san
HAVING count(DISTINCT game_id) >= 2;

-- Layer 1 overview: positions you keep reaching, and how you handle them.
CREATE OR REPLACE VIEW dashboard.repeated_positions AS
SELECT username, name, position_key,
       count(DISTINCT game_id) AS games,
       mode() WITHIN GROUP (ORDER BY san) AS usual_move,
       mode() WITHIN GROUP (ORDER BY best_san) AS engine_move,
       count(*) FILTER (WHERE is_error) AS errors,
       round((100.0 * count(*) FILTER (WHERE is_error) / count(*))::numeric, 1) AS error_rate,
       round(avg(win_loss)::numeric, 1) AS avg_win_loss,
       mode() WITHIN GROUP (ORDER BY opening) AS opening,
       min(move_number) AS move_number,
       min(colour) AS colour,
       min(fen_before) AS fen
FROM dashboard.player_moves
GROUP BY username, name, position_key
HAVING count(DISTINCT game_id) >= 3;

-- Layer 2: pawn structures you keep reaching, and how often you go wrong in them.
CREATE OR REPLACE VIEW dashboard.structure_mistakes AS
SELECT username, name, structure_key, min(structure) AS structure, colour,
       count(DISTINCT game_id) AS games,
       count(*) AS moves,
       count(*) FILTER (WHERE is_error) AS errors,
       count(*) FILTER (WHERE kind = 'positional') AS positional_errors,
       count(*) FILTER (WHERE kind IN ('allowed_tactic', 'missed_tactic')) AS tactical_errors,
       round((100.0 * count(*) FILTER (WHERE is_error) / count(*))::numeric, 1) AS error_rate,
       round(avg(win_loss)::numeric, 1) AS avg_win_loss,
       mode() WITHIN GROUP (ORDER BY opening) AS opening,
       (array_agg(url ORDER BY win_loss DESC))[1] AS worst_game
FROM dashboard.player_moves
WHERE phase <> 'opening'
GROUP BY username, name, structure_key, colour
HAVING count(DISTINCT game_id) >= 3;

-- Layer 3 and general breakdowns: every error with its context, for Grafana to slice.
CREATE OR REPLACE VIEW dashboard.errors AS
SELECT * FROM dashboard.player_moves WHERE is_error;

-- Every game by a tracked player, with Chess.com's accuracy (when Game Review was run) and ours (once analysed).
CREATE OR REPLACE VIEW dashboard.recent_games AS
SELECT g.id AS game_id, g.url, g.ended_at, g.rated, g.rules, g.mode, g.time_control,
       p.username, u.name, p.colour, p.rating, p.opponent, p.opponent_rating, p.outcome,
       p.accuracy AS chesscom_accuracy,
       CASE WHEN p.colour = 'white' THEN a.white_accuracy ELSE a.black_accuracy END AS stockfish_accuracy,
       a.opening,
       m.blunders, m.mistakes, m.inaccuracies
FROM chess.games g
JOIN chess.performances p ON p.game_id = g.id
JOIN chess.players u ON u.username = p.username
LEFT JOIN chess.analysed_games a ON a.game_id = g.id AND a.status = 'ok'
LEFT JOIN LATERAL (
    SELECT count(*) FILTER (WHERE classification = 'blunder') AS blunders,
           count(*) FILTER (WHERE classification = 'mistake') AS mistakes,
           count(*) FILTER (WHERE classification = 'inaccuracy') AS inaccuracies
    FROM chess.move_analysis x WHERE x.game_id = a.game_id AND x.colour = p.colour
) m ON a.game_id IS NOT NULL;

-- The window the analyser is configured for (ANALYSIS_DAYS), recorded on startup so the dashboards can show progress.
CREATE TABLE IF NOT EXISTS chess.analysis_settings (
    id boolean PRIMARY KEY DEFAULT true CHECK (id),
    days integer NOT NULL
);

CREATE OR REPLACE VIEW dashboard.analysis_status AS
SELECT u.username, u.name,
       count(g.id) AS games,
       count(a.game_id) FILTER (WHERE a.status = 'ok') AS analysed,
       count(a.game_id) FILTER (WHERE a.status = 'error') AS failed,
       count(g.id) FILTER (WHERE g.ended_at >= now() - interval '30 days') AS games_last_30_days,
       count(a.game_id) FILTER (WHERE a.status = 'ok' AND g.ended_at >= now() - interval '30 days') AS analysed_last_30_days,
       max(a.analysed_at) AS last_analysed_at,
       max(s.days) AS window_days,
       count(g.id) FILTER (WHERE in_window) AS games_in_window,
       count(a.game_id) FILTER (WHERE a.status = 'ok' AND in_window) AS analysed_in_window
FROM chess.players u
JOIN chess.performances p ON p.username = u.username
JOIN chess.games g ON g.id = p.game_id AND g.rules = 'chess'
LEFT JOIN chess.analysed_games a ON a.game_id = g.id
LEFT JOIN chess.analysis_settings s ON true
CROSS JOIN LATERAL (SELECT coalesce(s.days, 30) = 0 OR g.ended_at >= now() - make_interval(days => coalesce(s.days, 30)) AS in_window) w
GROUP BY u.username, u.name;

GRANT SELECT ON dashboard.player_moves, dashboard.repeated_mistakes, dashboard.repeated_positions,
    dashboard.structure_mistakes, dashboard.errors, dashboard.analysis_status, dashboard.recent_games TO grafana_reader;
