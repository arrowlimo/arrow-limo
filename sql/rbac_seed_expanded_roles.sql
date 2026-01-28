-- Expanded RBAC roles matching organizational structure
-- Similar to Windows admin groups: each role has specific module access

-- Clear old seed roles if needed (optional)
-- DELETE FROM system_role_permissions;
-- DELETE FROM system_roles;

-- Insert expanded roles
INSERT INTO system_roles (role_name, description)
VALUES
  ('super_user', 'Full system access; manage users, locks, configs, all data'),
  ('bookkeeper', 'Record payments, reconcile, view reports; no deletions'),
  ('accountant', 'Manage receipts, payments, GL, tax reporting; respects locks'),
  ('dispatch', 'Manage charters, customer records, assign drivers; no financial edits'),
  ('restricted_chauffeur', 'View assigned charters and vehicles; add notes; view own pay'),
  ('maintenance', 'View/edit vehicle maintenance logs, CVIP, HOS; view assigned vehicles'),
  ('city_auditor', 'Read-only access to charters, payments, receipts, GL; reporting'),
  ('manager', 'View/edit employees, vehicles, payroll, charters; reporting'),
  ('employee', 'View own charters, pay, vehicle assignments; add notes'),
  ('driver', 'View own charters, vehicles, CVIP/HOS; add notes; view own pay')
ON CONFLICT (role_name) DO NOTHING;

-- Define permissions for each role

-- Super User: ALL permissions
INSERT INTO system_role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM system_roles r
CROSS JOIN system_permissions p
WHERE r.role_name = 'super_user'
ON CONFLICT DO NOTHING;

-- Bookkeeper: record payments, reconcile, view reports (no deletions)
INSERT INTO system_role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM system_roles r, system_permissions p
WHERE r.role_name = 'bookkeeper'
  AND (
    (p.module IN ('payments', 'receipts') AND p.action IN ('view', 'add', 'edit'))
    OR (p.module = 'charters' AND p.action = 'view')
    OR (p.module = 'reporting' AND p.action = 'view')
    OR (p.module = 'notes' AND p.action IN ('add', 'edit'))
  )
ON CONFLICT DO NOTHING;

-- Accountant: full GL, payments, receipts (respects accounting locks)
INSERT INTO system_role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM system_roles r, system_permissions p
WHERE r.role_name = 'accountant'
  AND (
    (p.module IN ('payments', 'receipts', 'charters') AND p.action IN ('view', 'add', 'edit'))
    OR (p.module IN ('accounting', 'reporting') AND p.action = 'view')
    OR (p.module = 'notes' AND p.action IN ('add', 'edit'))
  )
ON CONFLICT DO NOTHING;

-- Dispatch: manage charters, customers, assign drivers (no finance)
INSERT INTO system_role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM system_roles r, system_permissions p
WHERE r.role_name = 'dispatch'
  AND (
    (p.module IN ('charters', 'employees') AND p.action IN ('view', 'add', 'edit'))
    OR (p.module = 'vehicles' AND p.action = 'view')
    OR (p.module = 'reporting' AND p.action = 'view')
    OR (p.module = 'notes' AND p.action IN ('add', 'edit'))
  )
ON CONFLICT DO NOTHING;

-- Restricted Chauffeur: view own charters/vehicles, add notes, view pay (read-only)
INSERT INTO system_role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM system_roles r, system_permissions p
WHERE r.role_name = 'restricted_chauffeur'
  AND (
    (p.module IN ('charters', 'vehicles', 'employees', 'payroll') AND p.action = 'view')
    OR (p.module IN ('vehicles_cvip', 'vehicles_hos') AND p.action = 'view')
    OR (p.module = 'notes' AND p.action IN ('add', 'edit'))
  )
ON CONFLICT DO NOTHING;

-- Maintenance: view/edit vehicles, maintenance logs; view CVIP/HOS
INSERT INTO system_role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM system_roles r, system_permissions p
WHERE r.role_name = 'maintenance'
  AND (
    (p.module = 'vehicles' AND p.action IN ('view', 'edit'))
    OR (p.module IN ('vehicles_cvip', 'vehicles_hos') AND p.action IN ('view', 'edit'))
    OR (p.module = 'notes' AND p.action IN ('add', 'edit'))
  )
ON CONFLICT DO NOTHING;

-- City Auditor: read-only access to key data (charters, payments, receipts, GL, reporting)
INSERT INTO system_role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM system_roles r, system_permissions p
WHERE r.role_name = 'city_auditor'
  AND (
    (p.module IN ('charters', 'payments', 'receipts', 'reporting') AND p.action = 'view')
    OR (p.module = 'notes' AND p.action = 'view')
  )
ON CONFLICT DO NOTHING;

-- Manager: view/edit employees, vehicles, payroll; view charters (no financial edits)
INSERT INTO system_role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM system_roles r, system_permissions p
WHERE r.role_name = 'manager'
  AND (
    (p.module IN ('charters', 'reporting') AND p.action = 'view')
    OR (p.module IN ('employees', 'vehicles', 'payroll') AND p.action IN ('view', 'edit'))
    OR (p.module = 'notes' AND p.action IN ('add', 'edit'))
  )
ON CONFLICT DO NOTHING;

-- Employee: view own records, add notes
INSERT INTO system_role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM system_roles r, system_permissions p
WHERE r.role_name = 'employee'
  AND (
    (p.module IN ('charters', 'employees', 'vehicles', 'payroll') AND p.action = 'view')
    OR (p.module = 'notes' AND p.action IN ('add', 'edit'))
  )
ON CONFLICT DO NOTHING;

-- Driver: view own charters/vehicles, add notes, view own pay (read-only)
INSERT INTO system_role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM system_roles r, system_permissions p
WHERE r.role_name = 'driver'
  AND (
    (p.module IN ('charters', 'employees', 'payroll') AND p.action = 'view')
    OR (p.module IN ('vehicles', 'vehicles_cvip', 'vehicles_hos') AND p.action = 'view')
    OR (p.module = 'notes' AND p.action IN ('add', 'edit'))
  )
ON CONFLICT DO NOTHING;
