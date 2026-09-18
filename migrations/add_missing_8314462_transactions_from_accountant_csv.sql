-- =====================================================================
-- Add 3 banking transactions missing from account 8314462 (CIBC
-- Vehicle Loans), discovered during verification against the old
-- accountant's CSV export (8314462_CIBC vehicle loans.csv)
-- =====================================================================
-- These 3 transactions appear in the accountant's bank verification
-- CSV but have no corresponding row anywhere in banking_transactions
-- (checked by reference number and by date/amount across all
-- accounts) - a true import gap, not a duplicate or misfiled entry.
--
-- Category is left as 'Needs Review' (not asserting a specific GL
-- code) since assigning the correct GL/expense category for driver
-- advances vs. income requires manual confirmation; the accountant's
-- own suggested category is preserved in reconciliation_notes for
-- reference.
-- =====================================================================

BEGIN;

DO $$
DECLARE
    v_count integer;
BEGIN
    SELECT count(*) INTO v_count FROM banking_transactions
    WHERE bank_id = 3
      AND transaction_date IN ('2018-08-31', '2018-09-04', '2018-09-10')
      AND ((debit_amount IN (450.00, 200.00, 205.00)) OR (credit_amount IN (450.00, 200.00, 205.00)));
    IF v_count <> 0 THEN
        RAISE EXCEPTION 'Expected 0 pre-existing matches for the 3 new transactions, found %', v_count;
    END IF;
END $$;

INSERT INTO banking_transactions
    (account_number, transaction_date, description, debit_amount, credit_amount,
     bank_id, category, reconciliation_status, reconciliation_notes, source_file)
VALUES
    ('8314462', '2018-08-31', 'E-TRANSFER 100860725784;NEW WEST ENTERTAINME NT;Internet Banking',
        NULL, 450.00, 3, 'Needs Review', 'unreconciled',
        'Added 2026-09-18 from accountant bank verification CSV (8314462_CIBC vehicle loans.csv); was missing from banking_transactions. Accountant suggested category: "4200 Other Charges"',
        '8314462_CIBC vehicle loans.csv'),
    ('8314462', '2018-09-04', 'E-TRANSFER 100864489293;Bill Gagne;Internet Banking',
        200.00, NULL, 3, 'Needs Review', 'unreconciled',
        'Added 2026-09-18 from accountant bank verification CSV (8314462_CIBC vehicle loans.csv); was missing from banking_transactions. Accountant suggested category: "1080 Petty Cash"',
        '8314462_CIBC vehicle loans.csv'),
    ('8314462', '2018-09-10', 'E-TRANSFER 100875864045;AMY KLEIN;Internet Banking',
        NULL, 205.00, 3, 'Needs Review', 'unreconciled',
        'Added 2026-09-18 from accountant bank verification CSV (8314462_CIBC vehicle loans.csv); was missing from banking_transactions. Accountant suggested category: "1375 Driver Advances"',
        '8314462_CIBC vehicle loans.csv');

DO $$
DECLARE
    v_count integer;
BEGIN
    SELECT count(*) INTO v_count FROM banking_transactions
    WHERE bank_id = 3
      AND source_file = '8314462_CIBC vehicle loans.csv';
    IF v_count <> 3 THEN
        RAISE EXCEPTION 'Expected 3 newly inserted transactions, found %', v_count;
    END IF;
END $$;

COMMIT;
