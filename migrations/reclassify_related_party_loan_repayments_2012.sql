-- =====================================================================
-- Reclassify 2012 "TRANSFER TO 8362" / "TRANSFER TO 00339/02-28362"
-- transactions as Related Party Loan Repayments (GL 2550)
-- =====================================================================
-- Context: User confirmed these "TRANSFER TO" banking entries are NOT
-- bank fees, NOT plain inter-account transfers, and NOT unrelated -
-- they are bank transfer payments made to repay a related-party loan
-- (the note "TRANSFER TO: 00339/02-28362" / "TRANSFER TO 8362" simply
-- identifies the destination account the loan repayment was wired to).
--
-- This matches the existing convention already used elsewhere in the
-- ledger for the same "CIBC 8362" destination (e.g. receipt 154787,
-- "Auto-created from banking (CIBC 8362 2014-2017)", GL 2550
-- "Related Party - Repayments Out", category 'Personal Draws').
--
-- Nine 2012 transactions were identified as this transfer-out pattern:
--   1. banking_transactions 101810  2012-01-03  $2,200.00  -> receipt 216321 (GL 5710 -> 2550)
--   2. banking_transactions 101903  2012-01-31  $1,800.00  -> receipt 216327 (GL 5710 -> 2550)
--   3. banking_transactions 101954  2012-02-28  $2,000.00  -> receipt 216333 (GL 5710 -> 2550)
--   4. banking_transactions  81772  2012-03-29  $2,000.00  -> no receipt (create new)
--   5. banking_transactions 102053  2012-04-05  $  750.00  -> receipt 216345 (GL 5710 -> 2550)
--   6. banking_transactions 102065  2012-04-10  $1,350.18  -> receipt 216346 (GL 5710 -> 2550)
--   7. banking_transactions 102102  2012-05-01  $  650.00  -> receipt 217963 (GL 1099 -> 2550)
--   8. banking_transactions  96804  2012-05-30  $2,500.00  -> receipt 216350 (GL 5710 -> 2550)
--   9. banking_transactions  82444  2012-12-28  $2,200.00  -> no receipt (create new)
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------
-- 1. Backups
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backup_related_party_transfer_reclass_20260918_receipts AS
SELECT * FROM receipts
WHERE receipt_id IN (216321, 216327, 216333, 216345, 216346, 217963, 216350);

CREATE TABLE IF NOT EXISTS backup_related_party_transfer_reclass_20260918_banking AS
SELECT * FROM banking_transactions
WHERE transaction_id IN (101810, 101903, 101954, 81772, 102053, 102065, 102102, 96804, 82444);

-- ---------------------------------------------------------------
-- 2. Verification guards - confirm the exact rows/amounts we expect
--    exist before mutating anything.
-- ---------------------------------------------------------------
DO $$
DECLARE
    v_count integer;
BEGIN
    SELECT count(*) INTO v_count FROM receipts
    WHERE receipt_id IN (216321, 216327, 216333, 216345, 216346, 217963, 216350);
    IF v_count <> 7 THEN
        RAISE EXCEPTION 'Expected 7 existing receipts, found %', v_count;
    END IF;

    SELECT count(*) INTO v_count FROM banking_transactions
    WHERE transaction_id IN (101810, 101903, 101954, 81772, 102053, 102065, 102102, 96804, 82444);
    IF v_count <> 9 THEN
        RAISE EXCEPTION 'Expected 9 existing banking_transactions rows, found %', v_count;
    END IF;

    IF EXISTS (SELECT 1 FROM banking_transactions WHERE transaction_id = 81772 AND receipt_id IS NOT NULL) THEN
        RAISE EXCEPTION 'banking_transactions 81772 unexpectedly already has a receipt_id';
    END IF;
    IF EXISTS (SELECT 1 FROM banking_transactions WHERE transaction_id = 82444 AND receipt_id IS NOT NULL) THEN
        RAISE EXCEPTION 'banking_transactions 82444 unexpectedly already has a receipt_id';
    END IF;
END $$;

-- ---------------------------------------------------------------
-- 3. Reclassify the 7 existing receipts to GL 2550
-- ---------------------------------------------------------------
UPDATE receipts
SET gl_account_code = '2550',
    gl_code = '2550',
    gl_account_name = 'Related Party - Repayments Out',
    category = 'Personal Draws',
    comment = COALESCE(comment || ' | ', '') || 'Reclassified 2026-09-18: bank transfer to CIBC 8362 = related party loan repayment, not a bank fee/inter-account clearing',
    accounting_status = 'RELATED_PARTY_LOAN_REPAYMENT',
    updated_at = now()
WHERE receipt_id IN (216321, 216327, 216333, 216345, 216346, 217963, 216350);

-- ---------------------------------------------------------------
-- 4. Create the 2 missing receipts for the unlinked banking rows
-- ---------------------------------------------------------------
INSERT INTO receipts (
    receipt_date, vendor_name, description, currency, gross_amount, gst_amount,
    expense_account, payment_method, source_hash, category, expense, revenue,
    net_amount, gl_account_code, gl_account_name, gl_code, auto_categorized,
    banking_transaction_id, is_transfer, verified_source, is_verified_banking,
    accounting_status, validation_status, source_system, source_reference
)
VALUES
(
    '2012-03-29', 'CIBC', 'TRANSFER TO 8362 - related party loan repayment', 'CAD',
    2000.00, 0.00, 'BANKING', 'bank_debit', 'AUTO_GENERATED', 'Personal Draws',
    2000.00, 0, 2000.00, '2550', 'Related Party - Repayments Out', '2550', TRUE,
    81772, FALSE, 'Auto-created 2026-09-18 from banking reconciliation (related party loan repayment audit)',
    TRUE, 'RELATED_PARTY_LOAN_REPAYMENT', 'PENDING', 'BANKING_IMPORT', 'BANKING_IMPORT'
),
(
    '2012-12-28', 'CIBC', 'TRANSFER TO 8362 - related party loan repayment', 'CAD',
    2200.00, 0.00, 'BANKING', 'bank_debit', 'AUTO_GENERATED', 'Personal Draws',
    2200.00, 0, 2200.00, '2550', 'Related Party - Repayments Out', '2550', TRUE,
    82444, FALSE, 'Auto-created 2026-09-18 from banking reconciliation (related party loan repayment audit)',
    TRUE, 'RELATED_PARTY_LOAN_REPAYMENT', 'PENDING', 'BANKING_IMPORT', 'BANKING_IMPORT'
);

-- ---------------------------------------------------------------
-- 5. Update banking_transactions: consistent category, status, and
--    link the two new receipts back to their source transactions.
-- ---------------------------------------------------------------
UPDATE banking_transactions
SET category = 'Related Party Loan Repayment',
    accounting_status = 'RELATED_PARTY_LOAN_REPAYMENT',
    reconciliation_notes = COALESCE(reconciliation_notes || ' | ', '') || 'Reclassified 2026-09-18: TRANSFER TO 8362 = related party loan repayment (per owner confirmation), not a bank fee',
    updated_at = now()
WHERE transaction_id IN (101810, 101903, 101954, 81772, 102053, 102065, 102102, 96804, 82444);

UPDATE banking_transactions b
SET receipt_id = r.receipt_id
FROM receipts r
WHERE b.transaction_id = 81772 AND r.banking_transaction_id = 81772;

UPDATE banking_transactions b
SET receipt_id = r.receipt_id
FROM receipts r
WHERE b.transaction_id = 82444 AND r.banking_transaction_id = 82444;

-- ---------------------------------------------------------------
-- 6. Final verification
-- ---------------------------------------------------------------
DO $$
DECLARE
    v_count integer;
BEGIN
    SELECT count(*) INTO v_count FROM receipts
    WHERE receipt_id IN (216321, 216327, 216333, 216345, 216346, 217963, 216350)
      AND gl_account_code = '2550';
    IF v_count <> 7 THEN
        RAISE EXCEPTION 'Expected 7 receipts on GL 2550 after update, found %', v_count;
    END IF;

    SELECT count(*) INTO v_count FROM receipts
    WHERE banking_transaction_id IN (81772, 82444) AND gl_account_code = '2550';
    IF v_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 new receipts on GL 2550, found %', v_count;
    END IF;

    SELECT count(*) INTO v_count FROM banking_transactions
    WHERE transaction_id IN (81772, 82444) AND receipt_id IS NULL;
    IF v_count <> 0 THEN
        RAISE EXCEPTION 'Expected both 81772 and 82444 banking rows to now have receipt_id set, % still NULL', v_count;
    END IF;

    SELECT count(*) INTO v_count FROM banking_transactions
    WHERE transaction_id IN (101810, 101903, 101954, 81772, 102053, 102065, 102102, 96804, 82444)
      AND category = 'Related Party Loan Repayment';
    IF v_count <> 9 THEN
        RAISE EXCEPTION 'Expected 9 banking_transactions recategorized, found %', v_count;
    END IF;
END $$;

COMMIT;
