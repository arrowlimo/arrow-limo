-- Delete existing Scotia Bank 2012 data
-- Backup table: scotia_2012_backup_20251105_232707
-- Generated: 2025-11-05 23:27:07.569289

BEGIN;

DELETE FROM banking_transactions 
WHERE account_number = '903990106011' 
  AND transaction_date >= '2012-01-01' 
  AND transaction_date <= '2012-12-31';

-- Check deletion
SELECT 'Deleted ' || ROW_COUNT() || ' rows' as result;

-- Rollback if you want to undo (comment out COMMIT, uncomment ROLLBACK):
COMMIT;
-- ROLLBACK;
