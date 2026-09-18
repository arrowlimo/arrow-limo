-- =====================================================================
-- Reclassify 2012 NATIONAL MONEYMART "load credit card for company
-- purchases" receipts to GL 1135 (Prepaid Visa Cards)
-- =====================================================================
-- Context: user spreadsheet cross-reference (SBS Accounting 2013
-- workbook, Sheet3) lists 6 MoneyMart transactions in 2012 labeled
-- "load credit card for company purchases". These are asset-side
-- prepaid-card loads (moving cash onto a prepaid Visa used for company
-- purchases), not bank fees, fuel, or owner personal draws.
--
-- Several other MoneyMart/"NATIONAL MONETM" receipts in 2012 already
-- correctly use GL 1135 "Prepaid Visa Cards" (e.g. 141744, 141855,
-- 140600, 215232, 140650) confirming that convention. The receipts
-- below were miscoded and are being brought in line with it:
--   141281  2012-02-07  $3,000.00  GL 5880 (Owner Personal)     -> 1135
--   142208  2012-05-18  $  300.00  GL 5110 (Fuel)                -> 1135
--   140446  2012-07-19  $  200.00  GL 5710 (Bank Fees)           -> 1135
--   150600  2012-08-31  $  750.00  GL 5710 (Bank Fees)           -> 1135
--   145315  2012-09-12  $  750.00  GL 5710 (Bank Fees)           -> 1135
--   139415  2012-10-19  $1,200.00  GL 5710 (Bank Fees)           -> 1135
--   140808  2012-11-26  $  910.00  GL 5710 (Bank Fees)           -> 1135
--   140969  2012-12-31  $  300.00  GL 5710 (Bank Fees)           -> 1135
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS backup_moneymart_prepaid_reclass_20260918_receipts AS
SELECT * FROM receipts
WHERE receipt_id IN (141281, 142208, 140446, 150600, 145315, 139415, 140808, 140969);

DO $$
DECLARE
    v_count integer;
BEGIN
    SELECT count(*) INTO v_count FROM receipts
    WHERE receipt_id IN (141281, 142208, 140446, 150600, 145315, 139415, 140808, 140969);
    IF v_count <> 8 THEN
        RAISE EXCEPTION 'Expected 8 existing receipts, found %', v_count;
    END IF;
END $$;

UPDATE receipts
SET gl_account_code = '1135',
    gl_code = '1135',
    gl_account_name = 'Prepaid Visa Cards',
    category = 'Prepaid Visa Cards',
    comment = COALESCE(comment || ' | ', '') || 'Reclassified 2026-09-18: MoneyMart credit-card load for company purchases, GL corrected to Prepaid Visa Cards (asset), not an expense',
    accounting_status = 'PREPAID_CARD_LOAD',
    updated_at = now()
WHERE receipt_id IN (141281, 142208, 140446, 150600, 145315, 139415, 140808, 140969);

UPDATE banking_transactions
SET category = 'Prepaid Visa Card Load',
    accounting_status = 'PREPAID_CARD_LOAD',
    reconciliation_notes = COALESCE(reconciliation_notes || ' | ', '') || 'Reclassified 2026-09-18: MoneyMart credit card load, not a bank fee/expense',
    updated_at = now()
WHERE transaction_id IN (81522, 82016, 69120, 82265, 69469, 69592, 69750);

DO $$
DECLARE
    v_count integer;
BEGIN
    SELECT count(*) INTO v_count FROM receipts
    WHERE receipt_id IN (141281, 142208, 140446, 150600, 145315, 139415, 140808, 140969)
      AND gl_account_code = '1135';
    IF v_count <> 8 THEN
        RAISE EXCEPTION 'Expected 8 receipts on GL 1135 after update, found %', v_count;
    END IF;
END $$;

COMMIT;
