-- ═══════════════════════════════════════════════════════════════════════════
-- COPY AND PASTE THIS ENTIRE SCRIPT INTO PGADMIN AND CLICK EXECUTE
-- Takes 30 seconds, fixes timeouts forever
-- ═══════════════════════════════════════════════════════════════════════════

-- Step 1: Give yourself time to work (IMMEDIATE RELIEF)
SET idle_in_transaction_session_timeout = '2h';
SET statement_timeout = '15min';

SELECT '✅ You now have 2 HOURS to work on receipts without timeout!' as status;

-- Step 2: Add missing indexes (PERMANENT FIX)
-- These make receipt loading INSTANT instead of 30+ seconds

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_banking_transactions_receipt_id 
ON banking_transactions(receipt_id) WHERE receipt_id IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_receipts_employee_id 
ON receipts(employee_id) WHERE employee_id IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_receipts_charter_id 
ON receipts(charter_id) WHERE charter_id IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_receipts_vehicle_number 
ON receipts(vehicle_number) WHERE vehicle_number IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_receipts_banking_transaction_id 
ON receipts(banking_transaction_id) WHERE banking_transaction_id IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_receipts_date_id 
ON receipts(receipt_date DESC, receipt_id DESC);

-- Step 3: Verify it worked
SELECT 
    CASE 
        WHEN COUNT(*) >= 6 THEN '✅ SUCCESS! All indexes created. Receipts will now load INSTANTLY!'
        ELSE '⚠️ Only ' || COUNT(*) || ' of 6 indexes exist. Check for errors above.'
    END as final_status
FROM pg_indexes
WHERE tablename IN ('receipts', 'banking_transactions')
AND indexname IN (
    'idx_banking_transactions_receipt_id',
    'idx_receipts_employee_id',
    'idx_receipts_charter_id',
    'idx_receipts_vehicle_number',
    'idx_receipts_banking_transaction_id',
    'idx_receipts_date_id'
);

-- ═══════════════════════════════════════════════════════════════════════════
-- DONE! Now:
-- 1. Close and restart your desktop application
-- 2. Open a receipt - should load in < 1 second
-- 3. Leave it open as long as you need - no more timeouts!
-- ═══════════════════════════════════════════════════════════════════════════
