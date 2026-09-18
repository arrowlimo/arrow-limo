-- =====================================================================
-- Correct Jack Carter April 2013 lease payment: mislabeled as NSF
-- =====================================================================
-- During the monthly lease payment audit, banking_transaction 78169
-- (2013-04-15, debit $1,885.65, description "NSF JACK CARTER",
-- is_nsf_charge=TRUE) was treated as a bounced payment and a matching
-- receipt (223810) was created and excluded from reports.
--
-- On deeper verification, EVERY other Jack Carter NSF debit in the
-- entire dataset (Jan/Feb/Aug/Sep/Oct/Nov 2012, Jan/Mar/May/Jul 2013)
-- has a matching "NSF RETURN JACK CARTER" credit of the same amount,
-- confirming the funds were reversed. Transaction 78169 has NO such
-- matching return anywhere in the banking_transactions table (checked
-- across the full dataset, not just nearby dates), and the account's
-- running balance confirms the $1,885.65 debit was never reversed -
-- the funds left the account and never came back.
--
-- This means the April 2013 payment actually cleared (real money left
-- and stayed gone), despite the bank's own memo/description text
-- calling it "NSF". The label appears to be a data artifact, not a
-- true bounce. Treating it as a real, non-excluded expense is the
-- correct, evidence-based treatment.
--
-- This migration corrects receipt 223810 to reflect that this was a
-- real payment, not an NSF exclusion, while keeping a clear audit
-- trail of the correction.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS backup_jack_carter_apr2013_nsf_correction_20260918_receipts AS
SELECT * FROM receipts WHERE receipt_id = 223810;

DO $$
DECLARE
    v_is_nsf boolean;
    v_bank_tx integer;
BEGIN
    SELECT is_nsf, banking_transaction_id INTO v_is_nsf, v_bank_tx
    FROM receipts WHERE receipt_id = 223810;
    IF v_bank_tx IS DISTINCT FROM 78169 THEN
        RAISE EXCEPTION 'Receipt 223810 not linked to expected banking_transaction 78169 (found %)', v_bank_tx;
    END IF;
    IF v_is_nsf IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Receipt 223810 was not in the expected pre-correction NSF state';
    END IF;
END $$;

UPDATE receipts
SET is_nsf = FALSE,
    exclude_from_reports = FALSE,
    accounting_status = NULL,
    validation_status = 'CORRECTED_FALSE_NSF_LABEL',
    comment = COALESCE(comment || ' | ', '') || 'Corrected 2026-09-18: bank memo says "NSF JACK CARTER" but no matching NSF RETURN credit exists anywhere in the banking data and the account balance was never restored, confirming the $1,885.65 actually left the account and was not reversed - reclassified as a real paid lease expense, not an NSF exclusion'
WHERE receipt_id = 223810;

DO $$
DECLARE
    v_count integer;
BEGIN
    SELECT count(*) INTO v_count FROM receipts
    WHERE receipt_id = 223810
      AND is_nsf = FALSE
      AND exclude_from_reports = FALSE
      AND validation_status = 'CORRECTED_FALSE_NSF_LABEL';
    IF v_count <> 1 THEN
        RAISE EXCEPTION 'Correction did not apply as expected to receipt 223810';
    END IF;
END $$;

COMMIT;
