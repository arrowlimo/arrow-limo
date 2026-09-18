-- =====================================================================
-- Correction (approved 2026-09-18): New West Entertainment deposit is
-- a charter payment, not "Other Charges"
-- =====================================================================
-- User confirmed transaction_id 111377 (2018-08-31, $450 deposit,
-- E-TRANSFER NEW WEST ENTERTAINME NT) is a charter client payment.
-- Reclassifying to the existing "Charter Income" category convention.
-- =====================================================================

BEGIN;

DO $$
DECLARE
    v_cat text;
BEGIN
    SELECT category INTO v_cat FROM banking_transactions WHERE transaction_id = 111377;
    IF v_cat IS DISTINCT FROM '4200 Other Charges' THEN
        RAISE EXCEPTION 'Expected pre-correction category "4200 Other Charges" on 111377, found %', v_cat;
    END IF;
END $$;

UPDATE banking_transactions
SET category = 'Charter Income',
    reconciliation_notes = 'Added 2026-09-18 (correction 1 of 3) from accountant bank verification CSV (8314462_CIBC vehicle loans.csv); was confirmed missing from banking_transactions. Category confirmed by user 2026-09-18: this is a charter client payment (Charter Income), not "4200 Other Charges" as first applied.'
WHERE transaction_id = 111377;

DO $$
DECLARE
    v_cat text;
BEGIN
    SELECT category INTO v_cat FROM banking_transactions WHERE transaction_id = 111377;
    IF v_cat IS DISTINCT FROM 'Charter Income' THEN
        RAISE EXCEPTION 'Correction did not apply as expected, category is %', v_cat;
    END IF;
END $$;

COMMIT;
