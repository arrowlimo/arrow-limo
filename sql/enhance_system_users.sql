-- Enhanced RBAC schema with password security fields

-- 1) Update system_users with password fields (if not already added)
ALTER TABLE system_users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);
ALTER TABLE system_users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMP;
ALTER TABLE system_users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP;
ALTER TABLE system_users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER DEFAULT 0;
ALTER TABLE system_users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP;

-- Add index for performance
CREATE INDEX IF NOT EXISTS idx_system_users_username ON system_users(username);
CREATE INDEX IF NOT EXISTS idx_system_users_is_active ON system_users(is_active);
