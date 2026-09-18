-- =====================================================================
-- Correction 3 of 3: add missing transaction (2018-09-10, $205 deposit,
-- E-TRANSFER Amy Klein) to account 8314462 (CIBC Vehicle Loans), per
-- accountant's bank verification CSV (8314462_CIBC vehicle loans.csv)
-- =====================================================================

BEGIN;

DO $$
DECLARE
    v_count integer;
BEGIN
    SELECT count(*) INTO v_count FROM banking_transactions
    WHERE bank_id = 3
      AND transaction_date = '2018-09-10'
      AND credit_amount = 205.00
      AND description ILIKE '%100875864045%';
    IF v_count <> 0 THEN
        RAISE EXCEPTION 'Expected 0 pre-existing matches, found %', v_count;
    END IF;
END $$;

INSERT INTO banking_transactions
    (account_number, transaction_date, description, debit_amount, credit_amount,
     bank_id, category, reconciliation_status, reconciliation_notes, source_file)
VALUES
    ('8314462', '2018-09-10', 'E-TRANSFER 100875864045;AMY KLEIN;Internet Banking',
        NULL, 205.00, 3, 'DRIVER_PAY_REIMBURSEMENT', 'unreconciled',
        'Added 2026-09-18 (correction 3 of 3) from accountant bank verification CSV (8314462_CIBC vehicle loans.csv); was confirmed missing from banking_transactions. Category per accountant suggestion "1375 Driver Advances".',
        '8314462_CIBC vehicle loans.csv');

DO $$
DECLARE
    v_count integer;
BEGIN
    SELECT count(*) INTO v_count FROM banking_transactions
    WHERE bank_id = 3
      AND transaction_date = '2018-09-10'
      AND credit_amount = 205.00
      AND description ILIKE '%100875864045%';
    IF v_count <> 1 THEN
        RAISE EXCEPTION 'Expected 1 inserted row, found %', v_count;
    END IF;
END $$;

COMMIT;
