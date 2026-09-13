-- 015: Three-way verification of cheque register, banking, and receipts.
--
-- A valid chain has one cheque-register row, one bank transaction, and one
-- non-void/non-NSF receipt. This migration only links records with matching
-- bank account, cheque number, exact cents amount, and a clearing date within
-- five days of the cheque date. It never creates or deletes receipts.

BEGIN;

CREATE TABLE IF NOT EXISTS backup_three_way_cheque_links_20260913 AS
SELECT cr.*
FROM cheque_register cr
WHERE FALSE;

INSERT INTO backup_three_way_cheque_links_20260913
SELECT cr.*
FROM cheque_register cr
WHERE cr.banking_transaction_id IS NULL
  AND COALESCE(cr.status, '') NOT ILIKE '%VOID%'
  AND COALESCE(cr.status, '') NOT ILIKE '%NSF%'
  AND COALESCE(cr.memo, '') NOT ILIKE '%NSF%'
  AND EXISTS (
      SELECT 1
      FROM banking_transactions bt
      WHERE bt.account_number = cr.account_number
        AND bt.check_number = cr.cheque_number
        AND ABS(COALESCE(bt.debit_amount, 0) - cr.amount) < 0.005
        AND bt.transaction_date BETWEEN
            COALESCE(cr.cheque_date, cr.cleared_date) - INTERVAL '5 days'
            AND COALESCE(cr.cheque_date, cr.cleared_date) + INTERVAL '5 days'
        AND COALESCE(bt.is_nsf_charge, FALSE) IS NOT TRUE
        AND COALESCE(bt.description, '') NOT ILIKE '%NSF%'
      GROUP BY cr.id
      HAVING COUNT(*) = 1
  )
  AND NOT EXISTS (
      SELECT 1
      FROM backup_three_way_cheque_links_20260913 backup
      WHERE backup.id = cr.id
  );

WITH deterministic_links AS (
    SELECT cr.id, MIN(bt.transaction_id) AS banking_transaction_id
    FROM cheque_register cr
    JOIN banking_transactions bt
      ON bt.account_number = cr.account_number
     AND bt.check_number = cr.cheque_number
     AND ABS(COALESCE(bt.debit_amount, 0) - cr.amount) < 0.005
     AND bt.transaction_date BETWEEN
         COALESCE(cr.cheque_date, cr.cleared_date) - INTERVAL '5 days'
         AND COALESCE(cr.cheque_date, cr.cleared_date) + INTERVAL '5 days'
     AND COALESCE(bt.is_nsf_charge, FALSE) IS NOT TRUE
     AND COALESCE(bt.description, '') NOT ILIKE '%NSF%'
    WHERE cr.banking_transaction_id IS NULL
      AND COALESCE(cr.status, '') NOT ILIKE '%VOID%'
      AND COALESCE(cr.status, '') NOT ILIKE '%NSF%'
      AND COALESCE(cr.memo, '') NOT ILIKE '%NSF%'
    GROUP BY cr.id
    HAVING COUNT(*) = 1
)
UPDATE cheque_register cr
SET banking_transaction_id = dl.banking_transaction_id
FROM deterministic_links dl
WHERE cr.id = dl.id;

-- Bank source descriptions are not rewritten. Fill only the blank structured
-- recipient field from the checked register, giving the banking screen the
-- payee clarity without altering imported evidence.
UPDATE banking_transactions bt
SET check_recipient = cr.payee
FROM cheque_register cr
WHERE bt.transaction_id = cr.banking_transaction_id
  AND NULLIF(TRIM(bt.check_recipient), '') IS NULL
  AND NULLIF(TRIM(cr.payee), '') IS NOT NULL
  AND COALESCE(cr.status, '') NOT ILIKE '%VOID%'
  AND COALESCE(cr.status, '') NOT ILIKE '%NSF%'
  AND COALESCE(cr.memo, '') NOT ILIKE '%NSF%';

CREATE OR REPLACE VIEW v_three_way_cheque_verification AS
WITH eligible_cheques AS (
    SELECT cr.*
    FROM cheque_register cr
    WHERE COALESCE(cr.status, '') NOT ILIKE '%VOID%'
      AND COALESCE(cr.status, '') NOT ILIKE '%NSF%'
      AND COALESCE(cr.memo, '') NOT ILIKE '%NSF%'
),
receipt_links AS (
    SELECT
        bt.transaction_id,
        COUNT(DISTINCT r.receipt_id) AS receipt_count,
        STRING_AGG(DISTINCT r.receipt_id::text, ', ' ORDER BY r.receipt_id::text)
            AS receipt_ids,
        MIN(r.receipt_id) AS receipt_id,
        MIN(r.vendor_name) AS receipt_vendor,
        MIN(r.gross_amount) AS receipt_amount,
        MIN(r.description) AS receipt_description
    FROM banking_transactions bt
    LEFT JOIN receipts r
      ON (
          r.banking_transaction_id = bt.transaction_id
          OR r.receipt_id = bt.receipt_id
          OR r.receipt_id = bt.reconciled_receipt_id
      )
     AND COALESCE(r.is_nsf, FALSE) IS NOT TRUE
     AND COALESCE(r.is_voided, FALSE) IS NOT TRUE
    GROUP BY bt.transaction_id
)
SELECT
    cr.id AS cheque_id,
    cr.account_number,
    cr.cheque_number,
    cr.cheque_date,
    cr.cleared_date,
    cr.payee,
    cr.amount AS cheque_amount,
    cr.banking_transaction_id,
    bt.transaction_date AS bank_date,
    bt.description AS bank_description,
    bt.debit_amount AS bank_amount,
    bt.check_recipient AS bank_payee,
    rl.receipt_count,
    rl.receipt_ids,
    rl.receipt_id,
    rl.receipt_vendor,
    rl.receipt_amount,
    rl.receipt_description,
    CASE
        WHEN cr.banking_transaction_id IS NULL THEN 'CHECKBOOK_NO_BANK'
        WHEN bt.transaction_id IS NULL THEN 'BROKEN_BANK_LINK'
        WHEN ABS(COALESCE(bt.debit_amount, 0) - cr.amount) >= 0.005
            THEN 'CHECK_BANK_AMOUNT_MISMATCH'
        WHEN NULLIF(TRIM(bt.check_number), '') IS NOT NULL
             AND bt.check_number <> cr.cheque_number
            THEN 'CHECK_NUMBER_MISMATCH'
        WHEN COALESCE(rl.receipt_count, 0) = 0 THEN 'BANK_NO_RECEIPT'
        WHEN rl.receipt_count > 1 THEN 'MULTIPLE_RECEIPTS'
        WHEN ABS(COALESCE(rl.receipt_amount, 0) - cr.amount) >= 0.005
            THEN 'RECEIPT_AMOUNT_MISMATCH'
        ELSE 'VERIFIED'
    END AS verification_status
FROM eligible_cheques cr
LEFT JOIN banking_transactions bt
  ON bt.transaction_id = cr.banking_transaction_id
LEFT JOIN receipt_links rl
  ON rl.transaction_id = bt.transaction_id;

COMMIT;
