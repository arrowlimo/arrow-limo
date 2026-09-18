-- =====================================================================
-- Correction 2b: fix category on the Bill Gagne transaction added in
-- correction 2/3 (transaction_id 111378)
-- =====================================================================
-- Error found: the accountant's CSV actually categorizes this row as
-- "1375 Driver Advances", not "1080 Petty Cash" as was mistakenly
-- stated and applied in migrations/correction_2of3_add_8314462_20180904_billgagne.sql.
-- Correcting the category to match the source CSV.
-- =====================================================================

BEGIN;

DO $$
DECLARE
    v_cat text;
BEGIN
    SELECT category INTO v_cat FROM banking_transactions WHERE transaction_id = 111378;
    IF v_cat IS DISTINCT FROM 'PETTY CASH FUNDING' THEN
        RAISE EXCEPTION 'Expected pre-correction category PETTY CASH FUNDING on 111378, found %', v_cat;
    END IF;
END $$;

UPDATE banking_transactions
SET category = 'DRIVER_PAY_REIMBURSEMENT',
    reconciliation_notes = 'Added 2026-09-18 (correction 2 of 3) from accountant bank verification CSV (8314462_CIBC vehicle loans.csv); was confirmed missing from banking_transactions. Category corrected 2026-09-18: accountant CSV actually says "1375 Driver Advances" (not "1080 Petty Cash" as first applied in error).'
WHERE transaction_id = 111378;

DO $$
DECLARE
    v_cat text;
BEGIN
    SELECT category INTO v_cat FROM banking_transactions WHERE transaction_id = 111378;
    IF v_cat IS DISTINCT FROM 'DRIVER_PAY_REIMBURSEMENT' THEN
        RAISE EXCEPTION 'Correction did not apply as expected, category is %', v_cat;
    END IF;
END $$;

COMMIT;
