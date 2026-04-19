-- Add Employer CPP and EI Columns to employee_pay_master
-- CRA Compliance: Track employer portions of payroll contributions
-- Run Date: February 16, 2026
-- 
-- CRA Requirements:
-- - CPP Employer = CPP Employee (1:1 matching contribution)
-- - EI Employer = EI Employee × 1.4 (140% rate for 2024-2026)

BEGIN;

-- Add columns
ALTER TABLE employee_pay_master
ADD COLUMN IF NOT EXISTS cpp_employer DECIMAL(10,2) DEFAULT 0.00,
ADD COLUMN IF NOT EXISTS ei_employer DECIMAL(10,2) DEFAULT 0.00;

-- Backfill CPP employer (1:1 matching)
UPDATE employee_pay_master
SET cpp_employer = cpp_employee
WHERE cpp_employer IS NULL OR cpp_employer = 0;

-- Backfill EI employer (1.4× employee)
UPDATE employee_pay_master
SET ei_employer = ROUND(ei_employee * 1.4, 2)
WHERE ei_employer IS NULL OR ei_employer = 0;

COMMIT;

-- Verify results
SELECT 
    fiscal_year,
    COUNT(*) as records,
    SUM(cpp_employee) as total_cpp_employee,
    SUM(cpp_employer) as total_cpp_employer,
    SUM(ei_employee) as total_ei_employee,
    SUM(ei_employer) as total_ei_employer
FROM employee_pay_master
GROUP BY fiscal_year
ORDER BY fiscal_year DESC;
