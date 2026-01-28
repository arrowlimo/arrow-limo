-- Role-Based Access Control (RBAC) Schema
-- Users → Roles → Permissions

-- 1) Users table (system users for authorization)
CREATE TABLE IF NOT EXISTS system_users (
  user_id SERIAL PRIMARY KEY,
  username VARCHAR(100) UNIQUE NOT NULL,
  email VARCHAR(100),
  full_name VARCHAR(200),
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- 2) Roles table
CREATE TABLE IF NOT EXISTS system_roles (
  role_id SERIAL PRIMARY KEY,
  role_name VARCHAR(50) UNIQUE NOT NULL,
  description TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- 3) User-Role assignments (many-to-many)
CREATE TABLE IF NOT EXISTS user_roles (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES system_users(user_id) ON DELETE CASCADE,
  role_id INTEGER NOT NULL REFERENCES system_roles(role_id) ON DELETE CASCADE,
  assigned_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, role_id)
);

-- 4) Permissions table (module × action)
CREATE TABLE IF NOT EXISTS permissions (
  permission_id SERIAL PRIMARY KEY,
  module VARCHAR(50) NOT NULL,
  action VARCHAR(20) NOT NULL,
  description TEXT,
  UNIQUE(module, action)
);

-- 5) Role-Permission assignments (many-to-many)
CREATE TABLE IF NOT EXISTS role_permissions (
  id SERIAL PRIMARY KEY,
  role_id INTEGER NOT NULL REFERENCES system_roles(role_id) ON DELETE CASCADE,
  permission_id INTEGER NOT NULL REFERENCES permissions(permission_id) ON DELETE CASCADE,
  UNIQUE(role_id, permission_id)
);

-- 6) Data scopes (restrict user access to specific records)
CREATE TABLE IF NOT EXISTS user_scopes (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES system_users(user_id) ON DELETE CASCADE,
  scope_type VARCHAR(50),  -- 'charter_id', 'vehicle_id', 'employee_id', 'account_number'
  scope_value VARCHAR(100),
  created_at TIMESTAMP DEFAULT NOW()
);

-- 7) Helper function: check if user has permission
CREATE OR REPLACE FUNCTION user_has_permission(
  p_user_id INTEGER,
  p_module VARCHAR,
  p_action VARCHAR
)
RETURNS BOOLEAN AS $$
DECLARE
  v_has_perm BOOLEAN;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM user_roles ur
    JOIN system_roles sr ON ur.role_id = sr.role_id
    JOIN role_permissions rp ON sr.role_id = rp.role_id
    JOIN permissions p ON rp.permission_id = p.permission_id
    WHERE ur.user_id = p_user_id
      AND p.module = p_module
      AND p.action = p_action
  ) INTO v_has_perm;
  RETURN COALESCE(v_has_perm, FALSE);
END;
$$ LANGUAGE plpgsql;

-- 8) Helper function: check if user is superuser
CREATE OR REPLACE FUNCTION user_is_superuser(p_user_id INTEGER)
RETURNS BOOLEAN AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM user_roles ur
    JOIN system_roles sr ON ur.role_id = sr.role_id
    WHERE ur.user_id = p_user_id AND sr.role_name = 'super_user'
  );
END;
$$ LANGUAGE plpgsql;

-- 9) Helper function: get user's scopes
CREATE OR REPLACE FUNCTION get_user_scopes(
  p_user_id INTEGER,
  p_scope_type VARCHAR
)
RETURNS TABLE(scope_value VARCHAR) AS $$
BEGIN
  RETURN QUERY
  SELECT us.scope_value::VARCHAR
  FROM user_scopes us
  WHERE us.user_id = p_user_id AND us.scope_type = p_scope_type;
END;
$$ LANGUAGE plpgsql;
