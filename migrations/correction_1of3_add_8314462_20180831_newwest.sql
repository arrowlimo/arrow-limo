-- =====================================================================
-- Correction 1 of 3: add missing transaction (2018-08-31, $450 deposit,
-- E-TRANSFER NEW WEST ENTERTAINME NT) to account 8314462 (CIBC Vehicle
-- Loans), per accountant's bank verification CSV
-- (8314462_CIBC vehicle loans.csv)
-- =====================================================================
-- Confirmed missing from banking_transactions in the live DB verification
-- report run 2026-09-18. Applied individually and explicitly this time,
-- per user direction to correct items one at a time.
--
-- Category set to accountant's suggested "4200 Other Charges" mapped to
-- our category label; left as a category note only (no GL account
-- auto-assigned to receipts) so it can still be reviewed/adjusted.
-- =====================================================================

BEGIN;

DO $$
DECLARE
    v_count integer;
BEGIN
    SELECT count(*) INTO v_count FROM banking_transactions
    WHERE bank_id = 3
      AND transaction_date = '2018-08-31'
      AND credit_amount = 450.00
      AND description ILIKE '%100860725784%';
    IF v_count <> 0 THEN
        RAISE EXCEPTION 'Expected 0 pre-existing matches, found %', v_count;
    END IF;
END $$;

INSERT INTO banking_transactions
    (account_number, transaction_date, description, debit_amount, credit_amount,
     bank_id, category, reconciliation_status, reconciliation_notes, source_file)
VALUES
    ('8314462', '2018-08-31', 'E-TRANSFER 100860725784;NEW WEST ENTERTAINME NT;Internet Banking',
        NULL, 450.00, 3, '4200 Other Charges', 'unreconciled',
        'Added 2026-09-18 (correction 1 of 3) from accountant bank verification CSV (8314462_CIBC vehicle loans.csv); was confirmed missing from banking_transactions. Category per accountant suggestion "4200 Other Charges".',
        '8314462_CIBC vehicle loans.csv');

DO $$
DECLARE
    v_count integer;
BEGIN
    SELECT count(*) INTO v_count FROM banking_transactions
    WHERE bank_id = 3
      AND transaction_date = '2018-08-31'
      AND credit_amount = 450.00
      AND description ILIKE '%100860725784%';
    IF v_count <> 1 THEN
        RAISE EXCEPTION 'Expected 1 inserted row, found %', v_count;
    END IF;
END $$;

COMMIT;
