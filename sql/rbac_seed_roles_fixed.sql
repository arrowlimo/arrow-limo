-- Seed 10 organizational roles with permissions

-- Insert roles
INSERT INTO system_roles (role_name, description) VALUES
  ('super_user', 'Full system access, manage users, locks, configs'),
  ('bookkeeper', 'Receipts, payments, reconciliation, no deletions'),
  ('accountant', 'GL entries, tax records, reports, respects locks'),
  ('dispatch', 'Charter management, driver scheduling, no financial edits'),
  ('restricted_chauffeur', 'View assigned charters only, add notes'),
  ('maintenance', 'View vehicle records, log maintenance'),
  ('city_auditor', 'Reporting and data access only'),
  ('manager', 'View reporting, driver/vehicle management, payroll reporting'),
  ('employee', 'View own charters and pay'),
  ('driver', 'View own charters and vehicles')
ON CONFLICT (role_name) DO NOTHING;

-- Insert permissions by module × action
INSERT INTO permissions (module, action, description) VALUES
  -- Charters
  ('charters', 'view', 'View charters'),
  ('charters', 'add', 'Create new charters'),
  ('charters', 'edit', 'Edit charter details'),
  ('charters', 'delete', 'Delete charters'),
  
  -- Payments
  ('payments', 'view', 'View payment records'),
  ('payments', 'add', 'Add payments'),
  ('payments', 'edit', 'Edit payment details'),
  ('payments', 'delete', 'Delete payments'),
  
  -- Receipts
  ('receipts', 'view', 'View receipts'),
  ('receipts', 'add', 'Add receipts'),
  ('receipts', 'edit', 'Edit receipt details'),
  ('receipts', 'delete', 'Delete receipts'),
  
  -- GL (General Ledger)
  ('gl', 'view', 'View GL entries'),
  ('gl', 'add', 'Create GL entries'),
  ('gl', 'edit', 'Edit GL entries'),
  ('gl', 'delete', 'Delete GL entries'),
  
  -- Vehicles
  ('vehicles', 'view', 'View vehicle records'),
  ('vehicles', 'add', 'Add new vehicles'),
  ('vehicles', 'edit', 'Edit vehicle details'),
  ('vehicles', 'delete', 'Delete vehicles'),
  ('vehicles', 'maintenance', 'Log maintenance'),
  
  -- Employees
  ('employees', 'view', 'View employee records'),
  ('employees', 'add', 'Add employees'),
  ('employees', 'edit', 'Edit employee details'),
  ('employees', 'delete', 'Delete employees'),
  
  -- Payroll
  ('payroll', 'view', 'View payroll records'),
  ('payroll', 'add', 'Create payroll entries'),
  ('payroll', 'edit', 'Edit payroll'),
  ('payroll', 'delete', 'Delete payroll'),
  ('payroll', 'approve', 'Approve payroll'),
  
  -- Reporting
  ('reports', 'view', 'View reports'),
  ('reports', 'export', 'Export report data'),
  ('reports', 'configure', 'Configure custom reports'),
  
  -- System Admin
  ('users', 'manage', 'Manage user accounts'),
  ('locks', 'manage', 'Manage accounting locks'),
  ('config', 'manage', 'Manage system configuration')
ON CONFLICT (module, action) DO NOTHING;

-- Assign permissions to roles
-- super_user: all permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT sr.role_id, p.permission_id
FROM system_roles sr, permissions p
WHERE sr.role_name = 'super_user'
ON CONFLICT DO NOTHING;

-- bookkeeper: receipts, payments (view, add, edit), no delete
INSERT INTO role_permissions (role_id, permission_id)
SELECT sr.role_id, p.permission_id
FROM system_roles sr, permissions p
WHERE sr.role_name = 'bookkeeper' AND p.module IN ('receipts', 'payments') AND p.action IN ('view', 'add', 'edit')
ON CONFLICT DO NOTHING;

-- accountant: GL, reports, receipts (view), respects locks
INSERT INTO role_permissions (role_id, permission_id)
SELECT sr.role_id, p.permission_id
FROM system_roles sr, permissions p
WHERE sr.role_name = 'accountant' AND p.module IN ('gl', 'reports', 'receipts') AND p.action IN ('view', 'add', 'edit')
ON CONFLICT DO NOTHING;

-- dispatch: charters, employees (view, add, edit), vehicles (view)
INSERT INTO role_permissions (role_id, permission_id)
SELECT sr.role_id, p.permission_id
FROM system_roles sr, permissions p
WHERE sr.role_name = 'dispatch' AND (
  (p.module = 'charters' AND p.action IN ('view', 'add', 'edit')) OR
  (p.module = 'employees' AND p.action IN ('view', 'add', 'edit')) OR
  (p.module = 'vehicles' AND p.action = 'view')
)
ON CONFLICT DO NOTHING;

-- restricted_chauffeur: charters (view assigned only), add notes
INSERT INTO role_permissions (role_id, permission_id)
SELECT sr.role_id, p.permission_id
FROM system_roles sr, permissions p
WHERE sr.role_name = 'restricted_chauffeur' AND p.module = 'charters' AND p.action IN ('view', 'edit')
ON CONFLICT DO NOTHING;

-- maintenance: vehicles (view, maintenance)
INSERT INTO role_permissions (role_id, permission_id)
SELECT sr.role_id, p.permission_id
FROM system_roles sr, permissions p
WHERE sr.role_name = 'maintenance' AND p.module = 'vehicles' AND p.action IN ('view', 'maintenance')
ON CONFLICT DO NOTHING;

-- city_auditor: reports (view), gl (view)
INSERT INTO role_permissions (role_id, permission_id)
SELECT sr.role_id, p.permission_id
FROM system_roles sr, permissions p
WHERE sr.role_name = 'city_auditor' AND p.module IN ('reports', 'gl') AND p.action = 'view'
ON CONFLICT DO NOTHING;

-- manager: charters (view), employees (view), payroll (view, approve), vehicles (view), reports (view)
INSERT INTO role_permissions (role_id, permission_id)
SELECT sr.role_id, p.permission_id
FROM system_roles sr, permissions p
WHERE sr.role_name = 'manager' AND (
  (p.module IN ('charters', 'employees', 'vehicles', 'reports') AND p.action = 'view') OR
  (p.module = 'payroll' AND p.action IN ('view', 'approve'))
)
ON CONFLICT DO NOTHING;

-- employee: charters (view), payroll (view)
INSERT INTO role_permissions (role_id, permission_id)
SELECT sr.role_id, p.permission_id
FROM system_roles sr, permissions p
WHERE sr.role_name = 'employee' AND p.module IN ('charters', 'payroll') AND p.action = 'view'
ON CONFLICT DO NOTHING;

-- driver: charters (view), vehicles (view)
INSERT INTO role_permissions (role_id, permission_id)
SELECT sr.role_id, p.permission_id
FROM system_roles sr, permissions p
WHERE sr.role_name = 'driver' AND p.module IN ('charters', 'vehicles') AND p.action = 'view'
ON CONFLICT DO NOTHING;
