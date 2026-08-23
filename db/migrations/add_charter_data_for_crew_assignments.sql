ALTER TABLE charters
    ADD COLUMN IF NOT EXISTS charter_data JSONB NOT NULL DEFAULT '{}'::jsonb;