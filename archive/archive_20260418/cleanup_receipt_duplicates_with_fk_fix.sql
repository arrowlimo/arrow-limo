-- ============================================================================
-- CLEANUP RECEIPT DUPLICATES (Zero-Amount Banking Transaction Duplicates)
-- WITH FOREIGN KEY CLEANUP
-- Generated: 2026-02-14
-- Total receipts to delete: 968
-- ============================================================================

BEGIN;

-- Step 1: Create backup table
CREATE TABLE receipts_backup_20260214082902 AS
SELECT * FROM receipts
WHERE gross_amount = 0 
  AND banking_transaction_id IS NOT NULL
  AND created_from_banking = TRUE;

-- Verify backup created
SELECT COUNT(*) as backup_count FROM receipts_backup_20260214082902;
-- Expected: 968 rows in backup table

-- Step 2: Remove foreign key references from banking_transactions
-- Set receipt_id to NULL for banking transactions that point to these duplicate receipts
UPDATE banking_transactions
SET receipt_id = NULL
WHERE receipt_id IN (
    SELECT receipt_id 
    FROM receipts 
    WHERE gross_amount = 0 
      AND banking_transaction_id IS NOT NULL
      AND created_from_banking = TRUE
);

-- Step 3: Delete duplicate receipts
DELETE FROM receipts
WHERE gross_amount = 0 
  AND banking_transaction_id IS NOT NULL
  AND created_from_banking = TRUE;

-- Verify deletion count
SELECT COUNT(*) as deleted_count FROM receipts_backup_20260214082902;
-- Expected: 968 rows deleted

-- Verify cleanup
SELECT COUNT(*) as remaining_zero_amount
FROM receipts
WHERE gross_amount = 0 
  AND banking_transaction_id IS NOT NULL;

COMMIT;
