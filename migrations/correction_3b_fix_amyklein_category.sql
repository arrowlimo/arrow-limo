-- =====================================================================
-- Correction (approved 2026-09-18): Amy Klein deposit is a charter
-- payment, not a driver pay reimbursement
-- =====================================================================
-- User confirmed transaction_id 111379 (2018-09-10, $205 deposit,
-- E-TRANSFER AMY KLEIN) is a charter client payment.
-- Reclassifying to the existing "Charter Income" category convention.
-- =====================================================================

BEGIN;

DO $$
DECLARE
    v_cat text;
BEGIN
    SELECT category INTO v_cat FROM banking_transactions WHERE transaction_id = 111379;
    IF v_cat IS DISTINCT FROM 'DRIVER_PAY_REIMBURSEMENT' THEN
        RAISE EXCEPTION 'Expected pre-correction category DRIVER_PAY_REIMBURSEMENT on 111379, found %', v_cat;
    END IF;
END $$;

UPDATE banking_transactions
SET category = 'Charter Income',
    reconciliation_notes = 'Added 2026-09-18 (correction 3 of 3) from accountant bank verification CSV (8314462_CIBC vehicle loans.csv); was confirmed missing from banking_transactions. Category confirmed by user 2026-09-18: this is a charter client deposit (Charter Income), not a driver pay reimbursement as first applied.'
WHERE transaction_id = 111379;

DO $$
DECLARE
    v_cat text;
BEGIN
    SELECT category INTO v_cat FROM banking_transactions WHERE transaction_id = 111379;
    IF v_cat IS DISTINCT FROM 'Charter Income' THEN
        RAISE EXCEPTION 'Correction did not apply as expected, category is %', v_cat;
    END IF;
END $$;

COMMIT;
