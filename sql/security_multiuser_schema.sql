-- Enhanced security schema with password management and multi-user support

-- 1) Update users table with password & security fields
ALTER TABLE system_users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);
ALTER TABLE system_users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMP;
ALTER TABLE system_users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP;
ALTER TABLE system_users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER DEFAULT 0;
ALTER TABLE system_users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP;

-- 2) Password reset tokens (temporary, expire after 15 min)
CREATE TABLE IF NOT EXISTS password_reset_tokens (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES system_users(user_id),
  reset_token VARCHAR(255) UNIQUE NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP DEFAULT NOW() + INTERVAL '15 minutes',
  used_at TIMESTAMP
);

-- 3) Multi-user edit tracking (prevents "file in use" conflicts)
CREATE TABLE IF NOT EXISTS concurrent_edits (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES system_users(user_id),
  module VARCHAR(50) NOT NULL,
  record_type VARCHAR(50),  -- 'receipt', 'payment', 'charter', etc.
  record_id VARCHAR(100),
  checked_out_at TIMESTAMP DEFAULT NOW(),
  last_activity TIMESTAMP DEFAULT NOW(),
  checked_in_at TIMESTAMP
);

-- 4) Staging area for edits (user proposes changes, others see staging)
CREATE TABLE IF NOT EXISTS staged_edits (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES system_users(user_id),
  module VARCHAR(50) NOT NULL,
  record_type VARCHAR(50),
  record_id VARCHAR(100),
  table_name VARCHAR(100),
  original_values JSONB,  -- Original values before edit
  staged_values JSONB,    -- Proposed new values
  status VARCHAR(20) DEFAULT 'pending',  -- pending, committed, rolled_back, conflicted
  created_at TIMESTAMP DEFAULT NOW(),
  committed_at TIMESTAMP,
  conflicted_with_user_id INTEGER REFERENCES system_users(user_id),
  conflict_resolution VARCHAR(50)  -- 'keep_mine', 'keep_theirs', 'merge'
);

-- 5) Edit locks per record (prevent simultaneous edits)
CREATE TABLE IF NOT EXISTS record_locks (
  id SERIAL PRIMARY KEY,
  module VARCHAR(50) NOT NULL,
  record_type VARCHAR(50),
  record_id VARCHAR(100),
  locked_by_user_id INTEGER NOT NULL REFERENCES system_users(user_id),
  locked_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP DEFAULT NOW() + INTERVAL '10 minutes',
  UNIQUE(module, record_type, record_id)
);

-- 6) Security audit log (user authentication & access attempts)
CREATE TABLE IF NOT EXISTS security_audit_log (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES system_users(user_id),
  action VARCHAR(100) NOT NULL,  -- 'login', 'login_failed', 'password_reset', 'edit', etc.
  module VARCHAR(50),
  record_type VARCHAR(50),
  record_id VARCHAR(100),
  before_values JSONB,
  after_values JSONB,
  ip_address VARCHAR(50),
  success BOOLEAN DEFAULT TRUE,
  error_message TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- 7) Check if user can edit record (no lock exists)
CREATE OR REPLACE FUNCTION can_edit_record(
  p_user_id INTEGER,
  p_module VARCHAR,
  p_record_type VARCHAR,
  p_record_id VARCHAR
)
RETURNS TABLE(can_edit BOOLEAN, locked_by_username VARCHAR, reason TEXT) AS $$
BEGIN
  RETURN QUERY
  SELECT
    CASE WHEN rl.id IS NULL THEN TRUE ELSE FALSE END,
    su.username,
    CASE
      WHEN rl.id IS NULL THEN 'OK'
      WHEN rl.locked_by_user_id = p_user_id THEN 'Locked by you; edit in progress'
      WHEN rl.expires_at < NOW() THEN 'Lock expired; you can proceed (refreshing lock)'
      ELSE 'In use by ' || su.username || '; try again in 1 minute'
    END
  FROM (SELECT 1 dummy) d
  LEFT JOIN record_locks rl ON rl.module = p_module AND rl.record_type = p_record_type AND rl.record_id = p_record_id AND rl.expires_at > NOW()
  LEFT JOIN system_users su ON rl.locked_by_user_id = su.user_id;
END;
$$ LANGUAGE plpgsql;

-- 8) Acquire lock on record
CREATE OR REPLACE FUNCTION acquire_record_lock(
  p_user_id INTEGER,
  p_module VARCHAR,
  p_record_type VARCHAR,
  p_record_id VARCHAR
)
RETURNS BOOLEAN AS $$
BEGIN
  INSERT INTO record_locks (module, record_type, record_id, locked_by_user_id, expires_at)
  VALUES (p_module, p_record_type, p_record_id, p_user_id, NOW() + INTERVAL '10 minutes')
  ON CONFLICT (module, record_type, record_id) DO UPDATE
  SET locked_by_user_id = CASE WHEN record_locks.locked_by_user_id = p_user_id THEN p_user_id ELSE record_locks.locked_by_user_id END,
      expires_at = CASE WHEN record_locks.locked_by_user_id = p_user_id THEN NOW() + INTERVAL '10 minutes' ELSE record_locks.expires_at END;
  RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- 9) Release lock on record
CREATE OR REPLACE FUNCTION release_record_lock(
  p_user_id INTEGER,
  p_module VARCHAR,
  p_record_type VARCHAR,
  p_record_id VARCHAR
)
RETURNS BOOLEAN AS $$
BEGIN
  DELETE FROM record_locks
  WHERE module = p_module AND record_type = p_record_type AND record_id = p_record_id
    AND locked_by_user_id = p_user_id;
  RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- 10) Log user action to security audit log
CREATE OR REPLACE FUNCTION audit_user_action(
  p_user_id INTEGER,
  p_action VARCHAR,
  p_module VARCHAR,
  p_record_type VARCHAR,
  p_record_id VARCHAR,
  p_before_values JSONB DEFAULT NULL,
  p_after_values JSONB DEFAULT NULL,
  p_success BOOLEAN DEFAULT TRUE,
  p_error_message TEXT DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
  INSERT INTO security_audit_log (user_id, action, module, record_type, record_id, before_values, after_values, success, error_message)
  VALUES (p_user_id, p_action, p_module, p_record_type, p_record_id, p_before_values, p_after_values, p_success, p_error_message);
END;
$$ LANGUAGE plpgsql;
