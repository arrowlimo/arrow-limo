-- =====================================================================
-- Create missing NSF receipts for Jack Carter lease (audit-trail gap fix)
-- =====================================================================
-- Context: monthly lease payment verification for Jack Carter / vehicle
-- L-8 found 3 bank-confirmed NSF events with no corresponding receipt
-- record at all, unlike every other NSF month in this lease which has a
-- receipt. This creates the missing receipts so the audit trail is
-- complete and consistent with the rest of the lease history.
--   banking_transactions 102285  2012-09-17  $1,885.65  NSF (no receipt existed)
--   banking_transactions 102316  2012-10-15  $1,885.65  NSF (no receipt existed)
--   banking_transactions  78169  2013-04-15  $1,885.65  NSF (no receipt existed)
-- =====================================================================

BEGIN;

DO $$
DECLARE
    v_count integer;
BEGIN
    SELECT count(*) INTO v_count FROM banking_transactions
    WHERE transaction_id IN (102285, 102316, 78169) AND receipt_id IS NULL;
    IF v_count <> 3 THEN
        RAISE EXCEPTION 'Expected 3 unlinked NSF banking rows, found %', v_count;
    END IF;
END $$;

INSERT INTO receipts (
    receipt_date, vendor_name, description, currency, gross_amount, gst_amount,
    expense_account, payment_method, source_hash, category, expense, revenue,
    net_amount, gl_account_code, gl_account_name, gl_code, auto_categorized,
    vehicle_id, vehicle_number, banking_transaction_id, is_transfer,
    is_nsf, exclude_from_reports, accounting_status, accounting_exclusion_reason,
    validation_status, source_system, source_reference, comment
)
VALUES
(
    '2012-09-17', 'JACK CARTER', 'NSF JACK CARTER', 'CAD', 1885.65, 0.00,
    'BANKING', 'bank_debit', 'AUTO_GENERATED', 'Vehicle Lease Payments', 1885.65, 0,
    1885.65, '5150', 'Vehicle Lease Payments', '5150', TRUE,
    6, 'L-8', 102285, FALSE,
    TRUE, TRUE, 'NSF_NON_EXPENSE', 'NSF bounced lease payment, no accounting expense recorded',
    'PENDING', 'BANKING_IMPORT', 'BANKING_IMPORT',
    'Created 2026-09-18: missing receipt for confirmed NSF bank transaction 102285 during monthly lease payment audit'
),
(
    '2012-10-15', 'JACK CARTER', 'NSF JACK CARTER', 'CAD', 1885.65, 0.00,
    'BANKING', 'bank_debit', 'AUTO_GENERATED', 'Vehicle Lease Payments', 1885.65, 0,
    1885.65, '5150', 'Vehicle Lease Payments', '5150', TRUE,
    6, 'L-8', 102316, FALSE,
    TRUE, TRUE, 'NSF_NON_EXPENSE', 'NSF bounced lease payment, no accounting expense recorded',
    'PENDING', 'BANKING_IMPORT', 'BANKING_IMPORT',
    'Created 2026-09-18: missing receipt for confirmed NSF bank transaction 102316 during monthly lease payment audit'
),
(
    '2013-04-15', 'JACK CARTER', 'NSF JACK CARTER', 'CAD', 1885.65, 0.00,
    'BANKING', 'bank_debit', 'AUTO_GENERATED', 'Vehicle Lease Payments', 1885.65, 0,
    1885.65, '5150', 'Vehicle Lease Payments', '5150', TRUE,
    6, 'L-8', 78169, FALSE,
    TRUE, TRUE, 'NSF_NON_EXPENSE', 'NSF bounced lease payment, no accounting expense recorded',
    'PENDING', 'BANKING_IMPORT', 'BANKING_IMPORT',
    'Created 2026-09-18: missing receipt for confirmed NSF bank transaction 78169 during monthly lease payment audit'
);

UPDATE banking_transactions b
SET receipt_id = r.receipt_id
FROM receipts r
WHERE b.transaction_id IN (102285, 102316, 78169) AND r.banking_transaction_id = b.transaction_id;

DO $$
DECLARE
    v_count integer;
BEGIN
    SELECT count(*) INTO v_count FROM banking_transactions
    WHERE transaction_id IN (102285, 102316, 78169) AND receipt_id IS NOT NULL;
    IF v_count <> 3 THEN
        RAISE EXCEPTION 'Expected 3 banking rows linked to new receipts, found %', v_count;
    END IF;
END $$;

COMMIT;
