-- Drop employee_qualifications junction table
DROP TABLE IF EXISTS employee_qualifications CASCADE;

-- Add 5 generic qualification/training date columns to employees
ALTER TABLE employees
    ADD COLUMN IF NOT EXISTS qualification_1_date date,
    ADD COLUMN IF NOT EXISTS qualification_2_date date,
    ADD COLUMN IF NOT EXISTS qualification_3_date date,
    ADD COLUMN IF NOT EXISTS qualification_4_date date,
    ADD COLUMN IF NOT EXISTS qualification_5_date date;
