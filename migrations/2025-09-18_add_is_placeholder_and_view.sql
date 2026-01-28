-- Add is_placeholder flag to charters and create a reporting view that excludes placeholders.
-- Also add a trigger to automatically mark placeholder rows on insert/update based on business rules.

BEGIN;

ALTER TABLE charters
    ADD COLUMN IF NOT EXISTS is_placeholder boolean NOT NULL DEFAULT false;

-- Trigger function to auto-mark placeholders
CREATE OR REPLACE FUNCTION mark_charter_placeholder()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    -- Basic rules: explicit statuses, or zero-dollar REF/AUDIT reserve placeholders
    IF (NEW.status IN ('refund_pair','AUDIT_REVIEW'))
       OR ((COALESCE(NEW.total_amount_due,0) = 0
            AND COALESCE(NEW.paid_amount,0) = 0)
           AND NEW.reserve_number ~ '^(REF|AUDIT)') THEN
        NEW.is_placeholder := true;
    ELSIF NEW.is_placeholder IS NULL THEN
        NEW.is_placeholder := false;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_mark_placeholder ON charters;
CREATE TRIGGER trg_mark_placeholder
BEFORE INSERT OR UPDATE ON charters
FOR EACH ROW EXECUTE FUNCTION mark_charter_placeholder();

-- Reportable view filters out placeholders centrally
CREATE OR REPLACE VIEW v_charters_reportable AS
SELECT *
FROM charters
WHERE is_placeholder = false;

-- Helpful partial index for quick filtering
CREATE INDEX IF NOT EXISTS idx_charters_is_placeholder_true
    ON charters (charter_id)
    WHERE is_placeholder = true;

COMMIT;
