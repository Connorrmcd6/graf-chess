#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=collector_password="$COLLECTOR_PASSWORD" \
  --set=reader_password="$GRAFANA_DB_PASSWORD" <<'SQL'
CREATE ROLE chess_owner LOGIN PASSWORD :'collector_password';
CREATE ROLE grafana_reader LOGIN PASSWORD :'reader_password';
REVOKE ALL ON DATABASE chess FROM PUBLIC;
GRANT CONNECT ON DATABASE chess TO chess_owner, grafana_reader;
GRANT CREATE ON DATABASE chess TO chess_owner;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
ALTER ROLE grafana_reader SET default_transaction_read_only = on;
ALTER ROLE grafana_reader SET statement_timeout = '10s';
ALTER ROLE grafana_reader CONNECTION LIMIT 10;
SQL
