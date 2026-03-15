-- Migration: Add odometer reading to receipts
-- Date: 2026-02-15
-- Purpose: Track vehicle odometer readings for maintenance receipts
--          For fuel tracking and maintenance record keeping

-- Add odometer_reading column to receipts table
ALTER TABLE receipts 
ADD COLUMN IF NOT EXISTS odometer_reading INTEGER;

COMMENT ON COLUMN receipts.odometer_reading IS 'Vehicle odometer/mileage reading at time of receipt (for maintenance & fuel tracking)';

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_receipts_odometer 
ON receipts(vehicle_id, odometer_reading) 
WHERE odometer_reading IS NOT NULL;

-- Verify the column was added
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'receipts' 
        AND column_name = 'odometer_reading'
    ) THEN
        RAISE NOTICE 'Column odometer_reading successfully added to receipts table';
    ELSE
        RAISE EXCEPTION 'Failed to add odometer_reading column';
    END IF;
END $$;
