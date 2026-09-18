-- =====================================================================
-- REVERT: remove 3 banking transactions added without user authorization
-- =====================================================================
-- migrations/add_missing_8314462_transactions_from_accountant_csv.sql
-- inserted 3 transactions into banking_transactions (account 8314462,
-- bank_id=3) based on a gap found while running a verification report.
-- The user asked only for a verification report, not a data change,
-- and did not authorize this insert. Reverting in full.
-- =====================================================================

BEGIN;

DO $$
DECLARE
    v_count integer;
BEGIN
    SELECT count(*) INTO v_count FROM banking_transactions
    WHERE transaction_id IN (111374, 111375, 111376)
      AND source_file = '8314462_CIBC vehicle loans.csv';
    IF v_count <> 3 THEN
        RAISE EXCEPTION 'Expected 3 rows to revert, found %', v_count;
    END IF;
END $$;

DELETE FROM banking_transactions
WHERE transaction_id IN (111374, 111375, 111376)
  AND source_file = '8314462_CIBC vehicle loans.csv';

DO $$
DECLARE
    v_count integer;
BEGIN
    SELECT count(*) INTO v_count FROM banking_transactions
    WHERE transaction_id IN (111374, 111375, 111376);
    IF v_count <> 0 THEN
        RAISE EXCEPTION 'Revert failed, % rows still present', v_count;
    END IF;
END $$;

COMMIT;
