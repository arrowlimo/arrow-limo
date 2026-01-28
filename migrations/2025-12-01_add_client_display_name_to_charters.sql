-- Migration: Add denormalized client_display_name to charters
-- Date: 2025-12-01
-- Purpose: Eliminate repeated '?column?' or missing client name by storing a synced copy of clients.client_name.
-- Safety: Non-destructive; adds column and triggers. Can be rolled back by dropping triggers + column.

BEGIN;

-- 1. Add column if not exists
ALTER TABLE charters ADD COLUMN IF NOT EXISTS client_display_name TEXT;

-- 2. Backfill from clients table where client_name available
UPDATE charters c
SET client_display_name = cl.client_name
FROM clients cl
WHERE c.client_id = cl.client_id
  AND cl.client_name IS NOT NULL
  AND (c.client_display_name IS NULL OR c.client_display_name <> cl.client_name);

-- 3. Create function to sync charters when client_id changes or client name updates
CREATE OR REPLACE FUNCTION trg_sync_charter_client_display_name()
RETURNS trigger AS $$
BEGIN
    -- If invoked from charters (insert/update): set display name based on current client_id
    IF TG_TABLE_NAME = 'charters' THEN
        IF NEW.client_id IS NOT NULL THEN
            SELECT client_name INTO NEW.client_display_name FROM clients WHERE client_id = NEW.client_id;
        END IF;
        RETURN NEW;
    END IF;

    -- If invoked from clients (name change): propagate to all related charters
    IF TG_TABLE_NAME = 'clients' THEN
        UPDATE charters SET client_display_name = NEW.client_name WHERE client_id = NEW.client_id;
        RETURN NEW;
    END IF;
    RETURN NEW;
END;$$ LANGUAGE plpgsql;

-- 4. Trigger on charters for insert/update
DROP TRIGGER IF EXISTS trg_charters_set_display_name ON charters;
CREATE TRIGGER trg_charters_set_display_name
BEFORE INSERT OR UPDATE ON charters
FOR EACH ROW EXECUTE FUNCTION trg_sync_charter_client_display_name();

-- 5. Trigger on clients for name changes
DROP TRIGGER IF EXISTS trg_clients_propagate_display_name ON clients;
CREATE TRIGGER trg_clients_propagate_display_name
AFTER UPDATE OF client_name ON clients
FOR EACH ROW EXECUTE FUNCTION trg_sync_charter_client_display_name();

COMMIT;

-- Verification queries (run manually):
-- SELECT COUNT(*) FROM charters WHERE client_display_name IS NULL;
-- SELECT charter_id, client_id, client_display_name FROM charters ORDER BY charter_id DESC LIMIT 10;
-- Optional backfill fallback for blanks (run separately after review):
-- UPDATE charters SET client_display_name = client_id::text
-- WHERE client_display_name IS NULL AND client_id IS NOT NULL;
