-- 017: Fill blank structured banking cheque numbers from matching evidence.
--
-- The original import text already states the cheque number for these rows,
-- but the separate banking_transactions.check_number field was blank. Only
-- fill it when the linked, non-NSF/non-void cheque-register row has:
--   * a numeric cheque number,
--   * the same exact cents amount, and
--   * that number as a standalone token in the original bank description.
-- This preserves the imported description and avoids deriving a number from
-- amount or payee alone.

BEGIN;

CREATE TABLE IF NOT EXISTS backup_banking_cheque_numbers_20260913 AS
SELECT bt.*
FROM banking_transactions bt
WHERE FALSE;

INSERT INTO backup_banking_cheque_numbers_20260913
SELECT bt.*
FROM banking_transactions bt
JOIN cheque_register cr
  ON cr.banking_transaction_id = bt.transaction_id
WHERE NULLIF(TRIM(bt.check_number), '') IS NULL
  AND cr.cheque_number ~ '^[0-9]+$'
  AND ABS(COALESCE(bt.debit_amount, 0) - cr.amount) < 0.005
  AND COALESCE(cr.status, '') NOT ILIKE '%VOID%'
  AND COALESCE(cr.status, '') NOT ILIKE '%NSF%'
  AND COALESCE(cr.memo, '') NOT ILIKE '%NSF%'
  AND COALESCE(bt.is_nsf_charge, FALSE) IS NOT TRUE
  AND COALESCE(bt.description, '') NOT ILIKE '%NSF%'
  AND COALESCE(bt.description, '') ~*
      ('(^|[^0-9])' || cr.cheque_number || '([^0-9]|$)')
  AND NOT EXISTS (
      SELECT 1
      FROM backup_banking_cheque_numbers_20260913 backup
      WHERE backup.transaction_id = bt.transaction_id
  );

UPDATE banking_transactions bt
SET check_number = cr.cheque_number
FROM cheque_register cr
WHERE cr.banking_transaction_id = bt.transaction_id
  AND NULLIF(TRIM(bt.check_number), '') IS NULL
  AND cr.cheque_number ~ '^[0-9]+$'
  AND ABS(COALESCE(bt.debit_amount, 0) - cr.amount) < 0.005
  AND COALESCE(cr.status, '') NOT ILIKE '%VOID%'
  AND COALESCE(cr.status, '') NOT ILIKE '%NSF%'
  AND COALESCE(cr.memo, '') NOT ILIKE '%NSF%'
  AND COALESCE(bt.is_nsf_charge, FALSE) IS NOT TRUE
  AND COALESCE(bt.description, '') NOT ILIKE '%NSF%'
  AND COALESCE(bt.description, '') ~*
      ('(^|[^0-9])' || cr.cheque_number || '([^0-9]|$)');

COMMIT;
