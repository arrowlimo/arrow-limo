-- Drop CVIP columns from employees (CVIP is for vehicles, not employees)
ALTER TABLE employees
    DROP COLUMN IF EXISTS cvip_certified,
    DROP COLUMN IF EXISTS cvip_expiry;
