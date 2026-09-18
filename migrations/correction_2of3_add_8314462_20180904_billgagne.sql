-- =====================================================================
-- Correction 2 of 3: add missing transaction (2018-09-04, $200 debit,
-- E-TRANSFER Bill Gagne) to account 8314462 (CIBC Vehicle Loans), per
-- accountant's bank verification CSV (8314462_CIBC vehicle loans.csv)
-- =====================================================================

BEGIN;

DO $$
DECLARE
    v_count integer;
BEGIN
    SELECT count(*) INTO v_count FROM banking_transactions
    WHERE bank_id = 3
      AND transaction_date = '2018-09-04'
      AND debit_amount = 200.00
      AND description ILIKE '%100864489293%';
    IF v_count <> 0 THEN
        RAISE EXCEPTION 'Expected 0 pre-existing matches, found %', v_count;
    END IF;
END $$;

INSERT INTO banking_transactions
    (account_number, transaction_date, description, debit_amount, credit_amount,
     bank_id, category, reconciliation_status, reconciliation_notes, source_file)
VALUES
    ('8314462', '2018-09-04', 'E-TRANSFER 100864489293;Bill Gagne;Internet Banking',
        200.00, NULL, 3, 'PETTY CASH FUNDING', 'unreconciled',
        'Added 2026-09-18 (correction 2 of 3) from accountant bank verification CSV (8314462_CIBC vehicle loans.csv); was confirmed missing from banking_transactions. Category per accountant suggestion "1080 Petty Cash".',
        '8314462_CIBC vehicle loans.csv');

DO $$
DECLARE
    v_count integer;
BEGIN
    SELECT count(*) INTO v_count FROM banking_transactions
    WHERE bank_id = 3
      AND transaction_date = '2018-09-04'
      AND debit_amount = 200.00
      AND description ILIKE '%100864489293%';
    IF v_count <> 1 THEN
        RAISE EXCEPTION 'Expected 1 inserted row, found %', v_count;
    END IF;
END $$;

COMMIT;
