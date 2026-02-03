-- Migration: Add locked flag to charters table
-- Purpose: Prevent further modifications to charters after audit actions complete
-- Created: 2026-02-02

BEGIN;

-- Add locked column if it doesn't exist
ALTER TABLE charters
ADD COLUMN IF NOT EXISTS locked BOOLEAN DEFAULT FALSE NOT NULL;

-- Add index for efficient queries filtering locked charters
CREATE INDEX IF NOT EXISTS idx_charters_locked ON charters(locked) WHERE locked = TRUE;

-- Commit transaction
COMMIT;
