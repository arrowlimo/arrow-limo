-- Clear WCB exemptions for family members (no exemption applies per WCB rules)
-- Safe to run multiple times

BEGIN;

-- Only proceed if columns exist
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='employees' AND column_name='wcb_exempt'
    ) THEN
        UPDATE employees
           SET wcb_exempt = FALSE,
               wcb_exemption_reason = NULL
         WHERE name ILIKE '%michael% richard%'
            OR name ILIKE '%mathew% richard%';
    END IF;
END $$;

COMMIT;
