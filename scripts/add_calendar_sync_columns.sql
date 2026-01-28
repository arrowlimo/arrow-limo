-- Add calendar sync tracking columns to charters table
-- Run this first to enable color-coded calendar synchronization

-- Add sync status column
ALTER TABLE charters 
ADD COLUMN IF NOT EXISTS calendar_sync_status VARCHAR(20) DEFAULT 'not_synced';

-- Add color for visual tracking
ALTER TABLE charters 
ADD COLUMN IF NOT EXISTS calendar_color VARCHAR(20);

-- Store Outlook entry ID for bidirectional sync
ALTER TABLE charters 
ADD COLUMN IF NOT EXISTS outlook_entry_id VARCHAR(255);

-- Store mismatch details
ALTER TABLE charters 
ADD COLUMN IF NOT EXISTS calendar_notes TEXT;

-- Add index for faster filtering
CREATE INDEX IF NOT EXISTS idx_charters_calendar_sync 
ON charters(calendar_sync_status, charter_date);

-- Color legend:
-- 'green'  = synced (perfect match)
-- 'red'    = not_in_calendar (missing from Outlook)
-- 'yellow' = mismatch (data differs)
-- 'blue'   = updated (recently synced)
-- 'gray'   = cancelled

-- Status values:
-- 'synced' = matched and up to date
-- 'not_in_calendar' = exists in DB but not in Outlook
-- 'mismatch' = exists in both but data differs
-- 'not_synced' = never checked
-- 'cancelled' = cancelled charter

COMMENT ON COLUMN charters.calendar_sync_status IS 'Sync status with Outlook calendar';
COMMENT ON COLUMN charters.calendar_color IS 'Visual indicator: green=synced, red=missing, yellow=mismatch, blue=updated, gray=cancelled';
COMMENT ON COLUMN charters.outlook_entry_id IS 'Outlook appointment EntryID for bidirectional sync';
COMMENT ON COLUMN charters.calendar_notes IS 'Mismatch details or sync notes';
