-- Add WCB exemption flags to employees and create effective compensation view
-- Safe to run multiple times: uses IF EXISTS/IF NOT EXISTS patterns where possible

BEGIN;

-- 1) Add WCB exemption columns to employees
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'employees' AND column_name = 'wcb_exempt'
    ) THEN
        EXECUTE 'ALTER TABLE employees ADD COLUMN wcb_exempt BOOLEAN NOT NULL DEFAULT FALSE';
        EXECUTE 'COMMENT ON COLUMN employees.wcb_exempt IS ''If TRUE, employee is WCB-exempt (e.g., family member owner-managed)''';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'employees' AND column_name = 'wcb_exemption_reason'
    ) THEN
        EXECUTE 'ALTER TABLE employees ADD COLUMN wcb_exemption_reason TEXT';
        EXECUTE 'COMMENT ON COLUMN employees.wcb_exemption_reason IS ''Reason/notes for WCB exemption''';
    END IF;
END $$;

-- 2) Mark specific family members as WCB-exempt (case-insensitive match on name)
UPDATE employees
   SET wcb_exempt = TRUE,
       wcb_exemption_reason = COALESCE(NULLIF(wcb_exemption_reason, ''), 'Family member (WCB-exempt)')
 WHERE (name ILIKE '%michael% richard%' OR name ILIKE '%mathew% richard%');

-- 3) Create a view that zeros WCB premium for exempt employees
--    The view preserves all columns from employee_monthly_compensation and overrides employer_wcb_premium via COALESCE
DROP VIEW IF EXISTS employee_monthly_compensation_effective;
CREATE VIEW employee_monthly_compensation_effective AS
SELECT 
    emc.*,
    CASE WHEN COALESCE(e.wcb_exempt, FALSE) THEN 0::numeric(12,2) ELSE COALESCE(emc.employer_wcb_premium, 0)::numeric(12,2) END AS employer_wcb_premium_effective
FROM employee_monthly_compensation emc
JOIN employees e ON e.id = emc.employee_id;

COMMENT ON VIEW employee_monthly_compensation_effective IS 'Monthly compensation joined to employees; includes employer_wcb_premium_effective that is zero when employee is WCB-exempt.';

COMMIT;
