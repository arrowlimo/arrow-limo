CREATE TABLE IF NOT EXISTS driver_auth_state (
    user_id INTEGER PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    must_change_password BOOLEAN NOT NULL DEFAULT TRUE,
    mfa_phone VARCHAR(20) NULL,
    phone_verified_at TIMESTAMPTZ NULL,
    password_changed_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS driver_user_links (
    user_id INTEGER PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    employee_id INTEGER NOT NULL UNIQUE REFERENCES employees(employee_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS driver_auth_challenges (
    challenge_hash CHAR(64) PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    purpose VARCHAR(32) NOT NULL,
    otp_hash CHAR(64) NULL,
    pending_phone VARCHAR(20) NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    send_count INTEGER NOT NULL DEFAULT 0,
    last_sent_at TIMESTAMPTZ NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_driver_auth_challenges_expiry
    ON driver_auth_challenges (expires_at);

CREATE TABLE IF NOT EXISTS driver_sms_rate_limits (
    user_id INTEGER PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    window_date DATE NOT NULL DEFAULT CURRENT_DATE,
    send_count INTEGER NOT NULL DEFAULT 0,
    last_sent_at TIMESTAMPTZ NULL
);

CREATE TABLE IF NOT EXISTS web_sessions (
    token_hash CHAR(64) PRIMARY KEY,
    employee_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    username TEXT NOT NULL,
    role TEXT NOT NULL,
    permissions JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_web_sessions_expiry
    ON web_sessions (expires_at)
    WHERE revoked_at IS NULL;
