-- Seed default role permissions

-- Admin: full access to everything
INSERT INTO system_role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM system_roles r, system_permissions p
WHERE r.role_name = 'admin'
ON CONFLICT DO NOTHING;

-- Accountant: financial records, respects accounting locks
INSERT INTO system_role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM system_roles r, system_permissions p
WHERE r.role_name = 'accountant'
  AND p.module IN ('payments', 'receipts', 'charters', 'accounting', 'reporting')
  AND (p.action IN ('view', 'add', 'edit') OR (p.module = 'payments' AND p.action = 'delete'))
ON CONFLICT DO NOTHING;

-- Manager: view reporting, manage driver/vehicle
INSERT INTO system_role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM system_roles r, system_permissions p
WHERE r.role_name = 'manager'
  AND (
    (p.module IN ('reporting', 'charters') AND p.action = 'view')
    OR (p.module IN ('employees', 'vehicles') AND p.action IN ('view', 'edit'))
    OR (p.module = 'payroll' AND p.action IN ('view', 'edit'))
  )
ON CONFLICT DO NOTHING;

-- Employee: view own records, add notes
INSERT INTO system_role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM system_roles r, system_permissions p
WHERE r.role_name = 'employee'
  AND (
    (p.module IN ('charters', 'employees', 'payroll') AND p.action = 'view')
    OR (p.module = 'notes' AND p.action IN ('add', 'edit'))
    OR (p.module = 'vehicles' AND p.action = 'view')
  )
ON CONFLICT DO NOTHING;

-- Driver: view own charters/vehicles, add notes, view pay (read-only)
INSERT INTO system_role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM system_roles r, system_permissions p
WHERE r.role_name = 'driver'
  AND (
    (p.module IN ('charters', 'employees') AND p.action = 'view')
    OR (p.module IN ('vehicles', 'vehicles_cvip', 'vehicles_hos', 'payroll') AND p.action = 'view')
    OR (p.module = 'notes' AND p.action IN ('add', 'edit'))
  )
ON CONFLICT DO NOTHING;
