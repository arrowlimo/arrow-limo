-- Make NSF and equivalent returned/reversal transactions easy to identify
-- and keep them out of accounting while preserving the bank audit trail.

BEGIN;

ALTER TABLE banking_transactions
    ADD COLUMN IF NOT EXISTS accounting_status varchar(32),
    ADD COLUMN IF NOT EXISTS accounting_exclusion_reason text;

ALTER TABLE receipts
    ADD COLUMN IF NOT EXISTS accounting_status varchar(32),
    ADD COLUMN IF NOT EXISTS accounting_exclusion_reason text;

COMMENT ON COLUMN banking_transactions.accounting_status IS
    'Accounting treatment: NSF_NON_EXPENSE for a bounced/returned/reversal '
    'transaction, otherwise REVIEW or ACCOUNTED.';

COMMENT ON COLUMN receipts.accounting_status IS
    'Accounting treatment: NSF_NON_EXPENSE means excluded from accounting '
    'reports but retained for reconciliation and audit.';

-- Direct NSF descriptions are authoritative and should never become an
-- expense merely because a receipt was auto-created or linked later.
UPDATE banking_transactions
SET is_nsf_charge = TRUE,
    category = 'NSF Return',
    accounting_status = 'NSF_NON_EXPENSE',
    accounting_exclusion_reason =
        'NSF/returned transaction; excluded from accounting',
    reconciliation_notes = COALESCE(
        reconciliation_notes || E'\n', ''
    ) || 'Classified as NSF/non-expense by standard NSF rules.',
    updated_at = CURRENT_TIMESTAMP
WHERE description ~* '(^|[^A-Z])(NSF|NON[- ]SUFFICIENT FUNDS|NSF RETURN|NSF REVERSAL|RETURNED NSF)([^A-Z]|$)';

-- Reversal/correction rows that do not literally say NSF are also marked
-- when an equal-and-opposite transaction exists in the same bank account
-- within ten days and one side explicitly identifies a return/reversal.
WITH reversal_pairs AS (
    SELECT DISTINCT
        original.transaction_id AS original_id,
        reversal.transaction_id AS reversal_id
    FROM banking_transactions original
    JOIN banking_transactions reversal
      ON reversal.account_number = original.account_number
     AND reversal.transaction_id <> original.transaction_id
     AND reversal.transaction_date BETWEEN original.transaction_date
                                       AND original.transaction_date + 10
     AND ROUND(COALESCE(original.debit_amount, 0)::numeric, 2)
         = ROUND(COALESCE(reversal.credit_amount, 0)::numeric, 2)
     AND ROUND(COALESCE(original.credit_amount, 0)::numeric, 2)
         = ROUND(COALESCE(reversal.debit_amount, 0)::numeric, 2)
     AND reversal.description ~*
         '(^|[^A-Z])(RETURN|RETURNED|REVERSAL|REVERSED|CORRECTION|CANCELLED)([^A-Z]|$)'
    WHERE original.debit_amount IS NOT NULL
      AND original.debit_amount > 0
)
UPDATE banking_transactions bt
SET accounting_status = 'NSF_NON_EXPENSE',
    accounting_exclusion_reason =
        'Equal-and-opposite returned/reversal transaction; excluded from accounting',
    updated_at = CURRENT_TIMESTAMP
FROM reversal_pairs pair
WHERE bt.transaction_id IN (pair.original_id, pair.reversal_id)
  AND COALESCE(bt.accounting_status, '') <> 'NSF_NON_EXPENSE';

UPDATE receipts r
SET is_nsf = TRUE,
    exclude_from_reports = TRUE,
    validation_status = 'NSF_CONFIRMED',
    validation_reason = COALESCE(
        r.validation_reason,
        'Linked banking transaction classified as NSF/returned'
    ),
    accounting_status = 'NSF_NON_EXPENSE',
    accounting_exclusion_reason =
        'NSF/returned transaction; excluded from accounting',
    updated_at = CURRENT_TIMESTAMP
FROM banking_transactions bt
WHERE bt.is_nsf_charge = TRUE
  AND (
      r.banking_transaction_id = bt.transaction_id
      OR r.receipt_id = bt.receipt_id
      OR r.receipt_id = bt.reconciled_receipt_id
  );

UPDATE receipts r
SET is_nsf = TRUE,
    exclude_from_reports = TRUE,
    validation_status = 'NSF_CONFIRMED',
    validation_reason = COALESCE(
        r.validation_reason,
        'Linked banking transaction classified as NSF/reversal'
    ),
    accounting_status = 'NSF_NON_EXPENSE',
    accounting_exclusion_reason =
        'NSF/reversal pair; excluded from accounting',
    updated_at = CURRENT_TIMESTAMP
FROM banking_transactions bt
WHERE bt.accounting_status = 'NSF_NON_EXPENSE'
  AND (
      r.banking_transaction_id = bt.transaction_id
      OR r.receipt_id = bt.receipt_id
      OR r.receipt_id = bt.reconciled_receipt_id
  );

DO $$
DECLARE
    unexcluded_nsf_receipts integer;
BEGIN
    SELECT COUNT(*)
    INTO unexcluded_nsf_receipts
    FROM receipts r
    JOIN banking_transactions bt
      ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.accounting_status = 'NSF_NON_EXPENSE'
      AND (
          COALESCE(r.is_nsf, FALSE) = FALSE
          OR COALESCE(r.exclude_from_reports, FALSE) = FALSE
          OR r.accounting_status <> 'NSF_NON_EXPENSE'
      );

    IF unexcluded_nsf_receipts <> 0 THEN
        RAISE EXCEPTION
            'Found % NSF-linked receipts still eligible for accounting',
            unexcluded_nsf_receipts;
    END IF;
END
$$;

COMMIT;
