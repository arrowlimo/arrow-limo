-- 016: Apply NSF exclusion consistently and expose the reverse bank audit.
--
-- A cheque register line may say CLEARED while its linked banking transaction
-- is an NSF reversal. The bank evidence wins for verification purposes, so
-- those lines are excluded from both three-way views.

CREATE OR REPLACE VIEW v_three_way_cheque_verification AS
WITH eligible_cheques AS (
    SELECT cr.*
    FROM cheque_register cr
    WHERE COALESCE(cr.status, '') NOT ILIKE '%VOID%'
      AND COALESCE(cr.status, '') NOT ILIKE '%NSF%'
      AND COALESCE(cr.memo, '') NOT ILIKE '%NSF%'
      AND NOT EXISTS (
          SELECT 1
          FROM banking_transactions excluded_bank
          WHERE excluded_bank.transaction_id = cr.banking_transaction_id
            AND (
                COALESCE(excluded_bank.is_nsf_charge, FALSE) IS TRUE
                OR COALESCE(excluded_bank.description, '') ILIKE '%NSF%'
            )
      )
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

CREATE OR REPLACE VIEW v_three_way_bank_verification AS
WITH eligible_bank_checks AS (
    SELECT bt.*
    FROM banking_transactions bt
    WHERE NULLIF(TRIM(bt.check_number), '') IS NOT NULL
      AND COALESCE(bt.is_nsf_charge, FALSE) IS NOT TRUE
      AND COALESCE(bt.description, '') NOT ILIKE '%NSF%'
),
eligible_cheques AS (
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
        MIN(r.gross_amount) AS receipt_amount
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
),
cheque_links AS (
    SELECT
        cr.banking_transaction_id,
        COUNT(*) AS cheque_count,
        STRING_AGG(cr.id::text, ', ' ORDER BY cr.id::text) AS cheque_ids,
        MIN(cr.cheque_number) AS cheque_number,
        MIN(cr.payee) AS cheque_payee,
        MIN(cr.amount) AS cheque_amount
    FROM eligible_cheques cr
    WHERE cr.banking_transaction_id IS NOT NULL
    GROUP BY cr.banking_transaction_id
)
SELECT
    bt.transaction_id AS banking_transaction_id,
    bt.account_number,
    bt.transaction_date AS bank_date,
    bt.check_number,
    bt.check_recipient AS bank_payee,
    bt.description AS bank_description,
    bt.debit_amount AS bank_amount,
    COALESCE(cl.cheque_count, 0) AS cheque_count,
    cl.cheque_ids,
    cl.cheque_number,
    cl.cheque_payee,
    cl.cheque_amount,
    rl.receipt_count,
    rl.receipt_ids,
    rl.receipt_id,
    rl.receipt_vendor,
    rl.receipt_amount,
    CASE
        WHEN COALESCE(cl.cheque_count, 0) = 0 THEN 'BANK_NO_CHECKBOOK'
        WHEN cl.cheque_count > 1 THEN 'MULTIPLE_CHECKBOOK_ENTRIES'
        WHEN ABS(COALESCE(cl.cheque_amount, 0) - COALESCE(bt.debit_amount, 0))
             >= 0.005 THEN 'CHECK_BANK_AMOUNT_MISMATCH'
        WHEN NULLIF(TRIM(bt.check_number), '') IS NOT NULL
             AND bt.check_number <> cl.cheque_number
            THEN 'CHECK_NUMBER_MISMATCH'
        WHEN COALESCE(rl.receipt_count, 0) = 0 THEN 'BANK_NO_RECEIPT'
        WHEN rl.receipt_count > 1 THEN 'MULTIPLE_RECEIPTS'
        WHEN ABS(COALESCE(rl.receipt_amount, 0) - COALESCE(bt.debit_amount, 0))
             >= 0.005 THEN 'RECEIPT_AMOUNT_MISMATCH'
        ELSE 'VERIFIED'
    END AS verification_status
FROM eligible_bank_checks bt
LEFT JOIN cheque_links cl
  ON cl.banking_transaction_id = bt.transaction_id
LEFT JOIN receipt_links rl
  ON rl.transaction_id = bt.transaction_id;
