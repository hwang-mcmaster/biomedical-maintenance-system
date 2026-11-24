-- Authentication, sessions, sign-in throttling and audit storage.
-- Applied by app.migrate after 004 (it extends workflow_technicians/workflow_events).
-- Re-runnable: every object uses IF NOT EXISTS, so an already set-up database is unchanged.
-- Manual use: psql -1 -f 005_authentication.sql (one transaction).
CREATE TABLE IF NOT EXISTS auth_users(id UUID PRIMARY KEY DEFAULT gen_random_uuid(), email VARCHAR(254) NOT NULL UNIQUE, name VARCHAR(100) NOT NULL,
 password_hash TEXT, role TEXT NOT NULL CHECK(role IN ('admin','coordinator','technician')), is_active BOOLEAN NOT NULL DEFAULT true,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS auth_sessions(token_hash TEXT PRIMARY KEY,user_id UUID NOT NULL REFERENCES auth_users(id),csrf_token TEXT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),last_seen TIMESTAMPTZ NOT NULL DEFAULT now(),expires_at TIMESTAMPTZ NOT NULL);
CREATE INDEX IF NOT EXISTS auth_session_user ON auth_sessions(user_id);
CREATE TABLE IF NOT EXISTS auth_tokens(token_hash TEXT PRIMARY KEY,user_id UUID NOT NULL REFERENCES auth_users(id),expires_at TIMESTAMPTZ NOT NULL);
CREATE TABLE IF NOT EXISTS auth_attempts(bucket TEXT PRIMARY KEY,failures INTEGER NOT NULL DEFAULT 0,window_start TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS auth_audit(id BIGSERIAL PRIMARY KEY,user_id UUID REFERENCES auth_users(id),action TEXT NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT now());
ALTER TABLE workflow_technicians ADD COLUMN IF NOT EXISTS user_id UUID UNIQUE REFERENCES auth_users(id);
ALTER TABLE workflow_events ADD COLUMN IF NOT EXISTS actor_id UUID REFERENCES auth_users(id);
