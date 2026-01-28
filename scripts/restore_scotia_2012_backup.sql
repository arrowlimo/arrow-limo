-- Restore Scotia Bank 2012 from backup
-- Backup table: scotia_2012_backup_20251105_232707
-- Generated: 2025-11-05 23:27:07.570624

BEGIN;

-- First delete current data
DELETE FROM banking_transactions 
WHERE account_number = '903990106011' 
  AND transaction_date >= '2012-01-01' 
  AND transaction_date <= '2012-12-31';

-- Restore from backup
INSERT INTO banking_transactions 
SELECT * FROM scotia_2012_backup_20251105_232707;

-- Check restoration
SELECT 'Restored ' || COUNT(*) || ' rows' as result
FROM banking_transactions 
WHERE account_number = '903990106011' 
  AND transaction_date >= '2012-01-01' 
  AND transaction_date <= '2012-12-31';

COMMIT;
