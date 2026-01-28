-- Role-Based Access Control (RBAC) Schema
-- Users → Roles → Permissions

-- 1) Users table (link to app auth or standalone)
CREATE TABLE IF NOT EXISTS system_users (
  user_id SERIAL PRIMARY KEY,
  username VARCHAR(100) UNIQUE NOT NULL,
  email VARCHAR(100),
  full_name VARCHAR(200),
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- 2) Roles
CREATE TABLE IF NOT EXISTS system_roles (
  role_id SERIAL PRIMARY KEY,
  role_name VARCHAR(50) UNIQUE NOT NULL,
  description TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Seed base roles
INSERT INTO system_roles (role_name, description)
VALUES
  ('admin', 'Full access to all modules and configurations'),
  ('accountant', 'Financial records, receipts, payments, GL; respects accounting locks'),
  ('manager', 'View reporting, driver/vehicle management, payroll'),
  ('employee', 'View own records (charters, pay); edit notes only'),
  ('driver', 'View own charters and assigned vehicles; edit notes; view own pay (read-only)')
ON CONFLICT DO NOTHING;

-- 3) Permissions (module × action)
CREATE TABLE IF NOT EXISTS system_permissions (
  permission_id SERIAL PRIMARY KEY,
  module VARCHAR(50) NOT NULL,  -- charters, payments, receipts, vehicles, employees, payroll, etc.
  action VARCHAR(20) NOT NULL,  -- view, add, edit, delete, approve
  description TEXT,
  UNIQUE(module, action)
);

-- Seed common permissions
INSERT INTO system_permissions (module, action, description)
VALUES
  ('charters', 'view', 'View charters'),
  ('charters', 'add', 'Create new charters'),
  ('charters', 'edit', 'Edit charter details'),
  ('charters', 'delete', 'Delete charters'),
  
  ('payments', 'view', 'View payment records'),
  ('payments', 'add', 'Record new payments'),
  ('payments', 'edit', 'Edit payment details'),
  ('payments', 'delete', 'Delete payment records'),
  
  ('receipts', 'view', 'View receipts'),
  ('receipts', 'add', 'Add new receipts'),
  ('receipts', 'edit', 'Edit receipt details'),
  ('receipts', 'delete', 'Delete receipts'),
  
  ('vehicles', 'view', 'View vehicle records'),
  ('vehicles', 'add', 'Add new vehicles'),
  ('vehicles', 'edit', 'Edit vehicle details'),
  ('vehicles', 'delete', 'Delete vehicles'),
  
  ('vehicles_cvip', 'view', 'View CVIP registration/inspection files'),
  ('vehicles_hos', 'view', 'View HOS (Hours of Service) logs'),
  
  ('employees', 'view', 'View employee records'),
  ('employees', 'add', 'Create employee records'),
  ('employees', 'edit', 'Edit employee details'),
  ('employees', 'delete', 'Delete employee records'),
  
  ('payroll', 'view', 'View payroll/pay stubs'),
  ('payroll', 'edit', 'Edit payroll (manager/admin only)'),
  
  ('notes', 'add', 'Add notes to records'),
  ('notes', 'edit', 'Edit own notes'),
  ('notes', 'delete', 'Delete own notes'),
  
  ('reporting', 'view', 'View financial and operational reports'),
  ('accounting', 'manage_locks', 'Enable/disable accounting locks')
ON CONFLICT DO NOTHING;

-- 4) Role-Permission mapping
CREATE TABLE IF NOT EXISTS system_role_permissions (
  id SERIAL PRIMARY KEY,
  role_id INTEGER NOT NULL REFERENCES system_roles(role_id),
  permission_id INTEGER NOT NULL REFERENCES system_permissions(permission_id),
  UNIQUE(role_id, permission_id)
);

-- 5) User-Role mapping
CREATE TABLE IF NOT EXISTS system_user_roles (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES system_users(user_id),
  role_id INTEGER NOT NULL REFERENCES system_roles(role_id),
  assigned_at TIMESTAMP DEFAULT NOW(),
  assigned_by VARCHAR(100),
  UNIQUE(user_id, role_id)
);

-- 6) Data scoping (for drivers/employees to see only own records)
CREATE TABLE IF NOT EXISTS system_user_scopes (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES system_users(user_id),
  scope_type VARCHAR(50),  -- 'charter_id', 'employee_id', 'vehicle_id', 'account_number'
  scope_value VARCHAR(100),
  created_at TIMESTAMP DEFAULT NOW()
);

-- 7) Check if user has permission for module+action
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
    SELECT 1
    FROM system_user_roles ur
    JOIN system_role_permissions rp ON ur.role_id = rp.role_id
    JOIN system_permissions p ON rp.permission_id = p.permission_id
    WHERE ur.user_id = p_user_id
      AND p.module = p_module
      AND p.action = p_action
  ) INTO v_has_perm;
  
  RETURN COALESCE(v_has_perm, FALSE);
END;
$$ LANGUAGE plpgsql;

-- 8) Check if user has role
CREATE OR REPLACE FUNCTION user_has_role(
  p_user_id INTEGER,
  p_role_name VARCHAR
)
RETURNS BOOLEAN AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1
    FROM system_user_roles ur
    JOIN system_roles r ON ur.role_id = r.role_id
    WHERE ur.user_id = p_user_id AND r.role_name = p_role_name
  );
END;
$$ LANGUAGE plpgsql;

-- 9) Get user's scopes (e.g., charter IDs driver can access)
CREATE OR REPLACE FUNCTION get_user_scopes(
  p_user_id INTEGER,
  p_scope_type VARCHAR
)
RETURNS TABLE(scope_value VARCHAR) AS $$
BEGIN
  RETURN QUERY
  SELECT sus.scope_value::VARCHAR
  FROM system_user_scopes sus
  WHERE sus.user_id = p_user_id AND sus.scope_type = p_scope_type;
END;
$$ LANGUAGE plpgsql;
