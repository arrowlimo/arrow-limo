-- Add is_out_of_town column to charters table for bylaw compliance tracking
-- Out-of-town runs are exempt from Red Deer driver-for-hire bylaw restrictions
-- and should be excluded from bylaw audit reports

ALTER TABLE charters
ADD COLUMN IF NOT EXISTS is_out_of_town BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN charters.is_out_of_town IS 'True if charter is outside Red Deer city limits - exempt from municipal bylaw requirements and excluded from bylaw audit reports';

-- Create index for bylaw audit queries
CREATE INDEX IF NOT EXISTS idx_charters_out_of_town ON charters(is_out_of_town) WHERE is_out_of_town = FALSE;
