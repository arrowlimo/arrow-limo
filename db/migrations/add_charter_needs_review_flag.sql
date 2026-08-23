ALTER TABLE charters
    ADD COLUMN IF NOT EXISTS needs_review BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE charters
SET needs_review = (
    COALESCE(cancelled, FALSE) = FALSE
    AND LOWER(COALESCE(status, '')) NOT IN ('closed', 'cancelled')
    AND charter_date <= CURRENT_DATE - 7
    AND ABS(COALESCE(balance_owing, 0)) > 0.01
);

CREATE OR REPLACE FUNCTION sync_charter_needs_review()
RETURNS TRIGGER AS $$
BEGIN
    NEW.needs_review := (
        COALESCE(NEW.cancelled, FALSE) = FALSE
        AND LOWER(COALESCE(NEW.status, '')) NOT IN ('closed', 'cancelled')
        AND NEW.charter_date <= CURRENT_DATE - 7
        AND ABS(COALESCE(NEW.balance_owing, 0)) > 0.01
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sync_charter_needs_review ON charters;

CREATE TRIGGER trg_sync_charter_needs_review
BEFORE INSERT OR UPDATE OF status, cancelled, balance_owing, charter_date ON charters
FOR EACH ROW
EXECUTE FUNCTION sync_charter_needs_review();

CREATE OR REPLACE VIEW charter_needs_review_queue AS
SELECT c.*
FROM charters c
WHERE COALESCE(c.cancelled, FALSE) = FALSE
    AND LOWER(COALESCE(c.status, '')) NOT IN ('closed', 'cancelled')
    AND c.charter_date <= CURRENT_DATE - 7
    AND ABS(COALESCE(c.balance_owing, 0)) > 0.01;