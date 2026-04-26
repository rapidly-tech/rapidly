-- ─────────────────────────────────────────────────────────────────────
-- Rapidly — bootstrap a read-only PostgreSQL role for local dev
--
-- Mounted into the postgres container via docker-compose as an
-- init script (/docker-entrypoint-initdb.d/).  Environment vars
-- are resolved at runtime by psql's \set + backtick syntax.
-- ─────────────────────────────────────────────────────────────────────

\set read_user `echo "$RAPIDLY_READ_USER"`
\set read_password `echo "$RAPIDLY_READ_PASSWORD"`
\set database_name `echo "$POSTGRES_DB"`

-- Role
CREATE USER :read_user WITH PASSWORD :'read_password';

-- Connection access
GRANT CONNECT ON DATABASE :database_name TO :read_user;
GRANT USAGE ON SCHEMA public TO :read_user;

-- Read-only on all current and future tables/sequences
GRANT SELECT ON ALL TABLES IN SCHEMA public TO :read_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO :read_user;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO :read_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE ON SEQUENCES TO :read_user;
