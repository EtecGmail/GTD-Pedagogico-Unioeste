CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'aluno'
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    token_hash TEXT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    role TEXT NOT NULL,
    created_at DOUBLE PRECISION NOT NULL,
    expires_at DOUBLE PRECISION NOT NULL,
    revoked_at DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id ON auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires_at ON auth_sessions(expires_at);

CREATE TABLE IF NOT EXISTS professors (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    email TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_professors_user_name ON professors (user_id, normalized_name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_professors_user_email ON professors (user_id, email);

CREATE TABLE IF NOT EXISTS disciplines (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    code TEXT NOT NULL,
    normalized_code TEXT NOT NULL,
    UNIQUE(user_id, normalized_name, normalized_code)
);

CREATE TABLE IF NOT EXISTS discipline_professor (
    discipline_id BIGINT NOT NULL,
    professor_id BIGINT NOT NULL,
    PRIMARY KEY (discipline_id, professor_id),
    FOREIGN KEY (discipline_id) REFERENCES disciplines(id),
    FOREIGN KEY (professor_id) REFERENCES professors(id)
);

CREATE TABLE IF NOT EXISTS inbox_items (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    content TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reading_plans (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    total_pages INTEGER NOT NULL,
    deadline_days INTEGER NOT NULL,
    daily_goal INTEGER NOT NULL,
    is_overloaded INTEGER NOT NULL,
    remaining_pages INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS acc_certificates (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    file_identifier TEXT NOT NULL UNIQUE,
    original_name TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    hours INTEGER,
    storage_key TEXT NOT NULL UNIQUE,
    metadata TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    token_hash TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_token_hash ON password_reset_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id ON password_reset_tokens(user_id);

CREATE TABLE IF NOT EXISTS security_events (
    id BIGSERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    result TEXT NOT NULL,
    user_id BIGINT,
    metadata TEXT NOT NULL
);
