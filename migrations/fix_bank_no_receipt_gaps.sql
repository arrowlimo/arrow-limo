-- Resolve the last 3 BANK_NO_RECEIPT gaps found via v_three_way_bank_verification.

-- 1) Receipt 141086 (Jeannette Soley payroll, $1690.68, cheque 206,
--    2012-01-09) is already correctly linked to banking_transaction 81406
--    with the right GL code (5210), but is flagged is_voided = TRUE even
--    though the cheque itself is CLEARED and no other receipt exists for
--    this payment. That flag appears to be an error -- un-void it so this
--    real, cleared payroll expense is properly counted.
UPDATE receipts
SET is_voided = FALSE
WHERE receipt_id = 141086;

-- 2) Receipt 218197 (Heffner Auto Lease, $1900.50, 2012-12-17) is a
--    duplicate of receipt 150650, which already correctly captures this
--    exact same lease payment with the proper banking_transaction_id link
--    (69709). 218197 came from a later, unlinked "auto_2012_unlinked_debit_
--    review_backfill" pass that never got de-duplicated against it. Mark
--    it a duplicate instead of deleting.
UPDATE receipts
SET exclude_from_reports = TRUE, potential_duplicate = TRUE, parent_receipt_id = 150650
WHERE receipt_id = 218197;

-- 3) Two Heffner Auto Finance (L-11) lease payments cleared the bank with
--    no receipt recorded at all: cheque 39 ($1900.50, 2012-12-24, bt 69734)
--    and cheque 40 ($1900.50, 2013-03-22, bt 78047). Create the missing
--    receipts, matching the GL code (5150 Vehicle Lease Payments) used by
--    every other Heffner L-11 lease payment receipt.
INSERT INTO receipts (
    receipt_date, vendor_name, description, currency, gross_amount, gst_amount,
    net_amount, revenue, gl_account_code, gl_code, banking_transaction_id,
    payment_method, business_personal, source_system, comment
) VALUES
    ('2012-12-24', 'HEFFNER AUTO FINANCE', 'CHQ 39 HEFFNER AUTO (L-11)', 'CAD', 1900.50, 90.50,
     1810.00, 0, '5150', '5150', 69734,
     'cheque', 'Business', 'cheque_book_audit_2026-09-14', 'Backfilled - cleared cheque had no receipt (cheque book audit)'),
    ('2013-03-22', 'HEFFNER AUTO FINANCE', 'CHQ 40 HEFFNER AUTO (L-11)', 'CAD', 1900.50, 90.50,
     1810.00, 0, '5150', '5150', 78047,
     'cheque', 'Business', 'cheque_book_audit_2026-09-14', 'Backfilled - cleared cheque had no receipt (cheque book audit)');
