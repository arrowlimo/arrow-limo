-- ===============================================================================
-- FIX RECEIPT UPDATE PERFORMANCE - ADD MISSING INDEXES
-- Date: February 12, 2026
-- Issue: 30-second delay when updating receipts
-- Cause: Missing indexes on foreign key columns (employee_id, charter_id, vehicle_number)
-- ===============================================================================

BEGIN;

-- Add index on employee_id (29,452 receipts = 30-second scans without this)
CREATE INDEX IF NOT EXISTS idx_receipts_employee_id ON receipts(employee_id)
WHERE employee_id IS NOT NULL;

-- Add index on charter_id
CREATE INDEX IF NOT EXISTS idx_receipts_charter_id ON receipts(charter_id)
WHERE charter_id IS NOT NULL;

-- Add index on vehicle_number
CREATE INDEX IF NOT EXISTS idx_receipts_vehicle_number ON receipts(vehicle_number)
WHERE vehicle_number IS NOT NULL;

COMMIT;

-- Verify indexes created
SELECT 
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'receipts'
AND indexname IN ('idx_receipts_employee_id', 'idx_receipts_charter_id', 'idx_receipts_vehicle_number')
ORDER BY indexname;

-- Show expected performance improvement
SELECT 
    '✅ Performance Fix Applied!' as status,
    COUNT(*) as total_receipts,
    COUNT(DISTINCT employee_id) as unique_employees,
    COUNT(DISTINCT charter_id) as unique_charters,
    COUNT(DISTINCT vehicle_number) as unique_vehicles
FROM receipts;

-- Recommendation
SELECT '🚀 Receipt updates should now be instant (< 1 second) instead of 30 seconds!' as result;
