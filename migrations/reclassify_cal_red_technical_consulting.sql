-- CAL RED TECHNICAL CONSULTING is Gordon Deans' own incorporated company,
-- which he uses to invoice Arrow Limo for his driving work (contract driver
-- pay routed through a driver-owned company, not a general professional/
-- consulting engagement, and not employee payroll withholding). The owner
-- already reviewed and confirmed receipt 214387 on 2026-09-05 as GL 5210
-- "Driver Wages & Reimbursements" with description "Contract driver pay
-- invoiced through driver-owned company" (receipt_review_status=reviewed,
-- receipt_reviewed_by='owner confirmation'). The other three receipts for
-- this same vendor were inconsistently coded to GL 5500 (Professional
-- Services - a non-postable header account) and GL 5870 (Miscellaneous
-- Business Expense). Standardize all four to GL 5210 to match the owner's
-- confirmed treatment, and record the same review confirmation on the
-- previously-unreviewed rows for audit consistency.

BEGIN;

CREATE TEMP TABLE cal_red_reclassification (
    receipt_id bigint PRIMARY KEY,
    target_gl_code text NOT NULL
) ON COMMIT DROP;

INSERT INTO cal_red_reclassification (receipt_id, target_gl_code)
SELECT receipt.receipt_id, '5210'
FROM receipts receipt
WHERE UPPER(TRIM(COALESCE(receipt.canonical_vendor, receipt.vendor_name)))
    = 'CAL RED TECHNICAL CONSULTING';

DO $$
DECLARE
    active_count integer;
    mapped_count integer;
BEGIN
    SELECT COUNT(*)
    INTO active_count
    FROM receipts
    WHERE UPPER(TRIM(COALESCE(canonical_vendor, vendor_name)))
        = 'CAL RED TECHNICAL CONSULTING';

    SELECT COUNT(*) INTO mapped_count FROM cal_red_reclassification;

    IF active_count <> 4 OR mapped_count <> active_count THEN
        RAISE EXCEPTION
            'Expected 4 CAL RED TECHNICAL CONSULTING receipts to map; active %, mapped %',
            active_count, mapped_count;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS backup_cal_red_gl_reclass_20260916 AS
SELECT receipt.*
FROM receipts receipt
JOIN cal_red_reclassification mapping
  ON mapping.receipt_id = receipt.receipt_id;

UPDATE receipts receipt
SET gl_account_code = mapping.target_gl_code,
    gl_account_name = account.account_name,
    gl_code = mapping.target_gl_code,
    gl_description = account.account_name,
    expense_account = mapping.target_gl_code,
    category = account.account_name,
    receipt_review_status = COALESCE(receipt.receipt_review_status, 'reviewed'),
    receipt_review_notes = COALESCE(
        receipt.receipt_review_notes,
        'Owner confirmed Cal Red invoices are contract driver pay (Gordon Deans'' driver-owned company); standardized to match receipt 214387.'
    ),
    receipt_reviewed_by = COALESCE(receipt.receipt_reviewed_by, 'owner confirmation'),
    receipt_reviewed_at = COALESCE(receipt.receipt_reviewed_at, CURRENT_TIMESTAMP),
    updated_at = CURRENT_TIMESTAMP
FROM cal_red_reclassification mapping
JOIN chart_of_accounts account
  ON account.account_code = mapping.target_gl_code
WHERE receipt.receipt_id = mapping.receipt_id;

DO $$
DECLARE
    incorrect_updates integer;
BEGIN
    SELECT COUNT(*)
    INTO incorrect_updates
    FROM cal_red_reclassification mapping
    JOIN receipts receipt ON receipt.receipt_id = mapping.receipt_id
    WHERE receipt.gl_account_code <> mapping.target_gl_code;

    IF incorrect_updates <> 0 THEN
        RAISE EXCEPTION
            'Expected zero incorrect CAL RED reclassifications, found %',
            incorrect_updates;
    END IF;
END
$$;

COMMIT;
