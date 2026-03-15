-- Migration: Increase fuel_amount precision to 3 decimals
-- Date: 2026-02-06
-- Purpose: Support precise fuel measurements (e.g., 183.085 liters)
-- Apply to: LOCAL almsdata database (already applied to Neon)

-- Change fuel_amount from numeric(12,2) to numeric(12,3)
ALTER TABLE receipts 
ALTER COLUMN fuel_amount TYPE numeric(12,3);

-- Verify the change
SELECT column_name, data_type, numeric_precision, numeric_scale 
FROM information_schema.columns 
WHERE table_name='receipts' AND column_name='fuel_amount';

-- Expected result: numeric_precision=12, numeric_scale=3
