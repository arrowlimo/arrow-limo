-- The February 2012 Scotia bank draft was purchased for $5,250, then
-- redeposited unused with extra cash for a $5,320 deposit. This is not a
-- vendor purchase and should not hit the P&L as an expense or revenue.
-- Preserve the true bank activity, keep the real bank service charges as
-- expenses, and mark the draft withdrawal/deposit pair plus the linked
-- receipt as non-accounting internal/correction movement.

BEGIN;

CREATE TABLE IF NOT EXISTS backup_scotia_bank_draft_return_20260917_banking AS
SELECT *
FROM banking_transactions
WHERE transaction_id IN (69022, 69023);

CREATE TABLE IF NOT EXISTS backup_scotia_bank_draft_return_20260917_receipts AS
SELECT *
FROM receipts
WHERE receipt_id = 140348;

DO $$
DECLARE
    draft_withdrawal_count integer;
    draft_deposit_count integer;
    linked_receipt_count integer;
BEGIN
    SELECT COUNT(*) INTO draft_withdrawal_count
    FROM banking_transactions
    WHERE transaction_id = 69022
      AND account_number = '903990106011'
      AND transaction_date = DATE '2012-02-23'
      AND ROUND(debit_amount::numeric, 2) = 5250.00;

    IF draft_withdrawal_count <> 1 THEN
        RAISE EXCEPTION
            'Expected Scotia draft withdrawal transaction 69022 for $5,250.00, found %',
            draft_withdrawal_count;
    END IF;

    SELECT COUNT(*) INTO draft_deposit_count
    FROM banking_transactions
    WHERE transaction_id = 69023
      AND account_number = '903990106011'
      AND transaction_date = DATE '2012-02-23'
      AND ROUND(credit_amount::numeric, 2) = 5320.00;

    IF draft_deposit_count <> 1 THEN
        RAISE EXCEPTION
            'Expected Scotia returned-draft deposit transaction 69023 for $5,320.00, found %',
            draft_deposit_count;
    END IF;

    SELECT COUNT(*) INTO linked_receipt_count
    FROM receipts
    WHERE receipt_id = 140348
      AND banking_transaction_id = 69022;

    IF linked_receipt_count <> 1 THEN
        RAISE EXCEPTION
            'Expected receipt 140348 to be linked to bank draft withdrawal 69022, found %',
            linked_receipt_count;
    END IF;
END
$$;

UPDATE banking_transactions
SET vendor_extracted = 'BANK DRAFT',
    category = 'Returned Bank Draft / Cash Movement',
    is_transfer = TRUE,
    accounting_status = 'BANK_DRAFT_RETURN_NON_EXPENSE',
    accounting_exclusion_reason =
        'Bank draft was purchased for $5,250 and redeposited unused with $70 extra cash; non-accounting cash movement, not a purchase expense.',
    reconciliation_status = 'reconciled',
    reconciliation_notes = COALESCE(reconciliation_notes || E'\n', '')
        || 'Returned unused bank draft pair: $5,250 withdrawal (69022) redeposited as part of $5,320 deposit (69023 = $5,250 draft + $70 cash). Exclude from accounting; preserve bank audit trail.',
    reconciled_at = COALESCE(reconciled_at, CURRENT_TIMESTAMP),
    reconciled_by = COALESCE(reconciled_by, 'bank_draft_reconciliation'),
    updated_at = CURRENT_TIMESTAMP
WHERE transaction_id IN (69022, 69023);

UPDATE receipts
SET vendor_name = 'BANK DRAFT',
    canonical_vendor = 'BANK DRAFT',
    description = 'Returned unused bank draft - redeposited with extra cash; non-accounting cash movement',
    is_transfer = TRUE,
    exclude_from_reports = TRUE,
    is_voided = FALSE,
    is_nsf = FALSE,
    gl_account_code = '6900',
    gl_code = '6900',
    gl_account_name = 'Uncategorized / Unknown',
    gl_description = 'Uncategorized / Unknown',
    expense_account = '6900',
    category = 'Returned Bank Draft / Cash Movement',
    accounting_status = 'BANK_DRAFT_RETURN_NON_EXPENSE',
    accounting_exclusion_reason =
        'Returned unused bank draft; excluded from accounting because the $5,250 withdrawal was redeposited in the $5,320 bank deposit.',
    validation_status = 'NON_ACCOUNTING_BANK_DRAFT_RETURN',
    validation_reason = 'Draft purchase was returned unused and redeposited; do not treat as expense.',
    receipt_review_status = 'reviewed',
    receipt_review_notes = COALESCE(receipt_review_notes || E'\n', '')
        || 'Owner confirmed bank draft was no longer required for purchase: $5,250 draft withdrawn, then redeposited with $70 extra cash as $5,320. Non-accounting bank/cash movement; exclude from accounting.',
    receipt_reviewed_at = COALESCE(receipt_reviewed_at, CURRENT_TIMESTAMP),
    receipt_reviewed_by = COALESCE(receipt_reviewed_by, 'owner confirmation'),
    updated_at = CURRENT_TIMESTAMP
WHERE receipt_id = 140348;

DO $$
DECLARE
    bad_receipt_count integer;
    bad_bank_count integer;
BEGIN
    SELECT COUNT(*) INTO bad_receipt_count
    FROM receipts
    WHERE receipt_id = 140348
      AND (
          COALESCE(exclude_from_reports, FALSE) = FALSE
          OR accounting_status <> 'BANK_DRAFT_RETURN_NON_EXPENSE'
          OR COALESCE(is_transfer, FALSE) = FALSE
      );

    IF bad_receipt_count <> 0 THEN
        RAISE EXCEPTION 'Returned bank draft receipt is still accounting-active';
    END IF;

    SELECT COUNT(*) INTO bad_bank_count
    FROM banking_transactions
    WHERE transaction_id IN (69022, 69023)
      AND (
          COALESCE(is_transfer, FALSE) = FALSE
          OR accounting_status <> 'BANK_DRAFT_RETURN_NON_EXPENSE'
      );

    IF bad_bank_count <> 0 THEN
        RAISE EXCEPTION 'Returned bank draft bank rows are not fully classified';
    END IF;
END
$$;

COMMIT;
