-- CAL RED TECHNICAL CONSULTING is paid as a vendor/subcontractor -- Gordon
-- Deans invoices Arrow Limo for his driving work through his own
-- incorporated company, rather than being paid as a T4 employee. GL 5210
-- (Driver Wages & Reimbursements) does not require an employee_id link
-- (chart_of_accounts.requires_employee = FALSE for 5210), and all 4 CAL RED
-- receipts already have employee_id = NULL, so none of this spend flows
-- into the employee-keyed T4 pipelines (employee_t4_records / driver_payroll)
-- automatically. This migration documents that intent explicitly on both the
-- vendor master record and the receipts, and updates the vendor's default
-- GL/category to match the standardized 5210 coding, so it stays clear this
-- is vendor/subcontractor spend, not payroll -- not T4 applicable.

BEGIN;

DO $$
DECLARE
    invalid_employee_link_count integer;
BEGIN
    SELECT COUNT(*)
    INTO invalid_employee_link_count
    FROM receipts
    WHERE UPPER(TRIM(COALESCE(canonical_vendor, vendor_name)))
        = 'CAL RED TECHNICAL CONSULTING'
      AND employee_id IS NOT NULL;

    IF invalid_employee_link_count <> 0 THEN
        RAISE EXCEPTION
            'Expected zero CAL RED receipts linked to an employee_id, found %',
            invalid_employee_link_count;
    END IF;
END
$$;

UPDATE vendor_accounts
SET default_gl_code = '5210',
    default_category = 'subcontractor_driver_pay',
    notes = TRIM(BOTH E'\n' FROM COALESCE(notes, '') || E'\n'
        || 'Subcontractor: driving services invoiced through Gordon Deans'' '
        || 'own corporation (Cal Red Technical Consulting). Paid as a '
        || 'vendor/subcontractor, NOT a T4 employee - no CPP/EI/tax '
        || 'withholding, no employee_id link, not eligible for T4 payroll '
        || 'treatment.')
WHERE canonical_vendor = 'CAL RED TECHNICAL CONSULTING'
  AND (notes IS NULL OR notes NOT ILIKE '%NOT a T4 employee%');

UPDATE receipts
SET receipt_review_notes = TRIM(BOTH E'\n' FROM COALESCE(receipt_review_notes, '') || E'\n'
        || 'Subcontractor/vendor payment (Gordon Deans'' corporation) - '
        || 'NOT T4 employment income; not subject to payroll withholding.')
WHERE UPPER(TRIM(COALESCE(canonical_vendor, vendor_name)))
    = 'CAL RED TECHNICAL CONSULTING'
  AND (receipt_review_notes IS NULL
       OR receipt_review_notes NOT ILIKE '%NOT T4 employment income%');

DO $$
DECLARE
    unnoted_receipt_count integer;
    vendor_note_count integer;
BEGIN
    SELECT COUNT(*)
    INTO unnoted_receipt_count
    FROM receipts
    WHERE UPPER(TRIM(COALESCE(canonical_vendor, vendor_name)))
        = 'CAL RED TECHNICAL CONSULTING'
      AND (receipt_review_notes IS NULL
           OR receipt_review_notes NOT ILIKE '%NOT T4 employment income%');

    IF unnoted_receipt_count <> 0 THEN
        RAISE EXCEPTION
            'Expected zero CAL RED receipts missing the non-T4 note, found %',
            unnoted_receipt_count;
    END IF;

    SELECT COUNT(*)
    INTO vendor_note_count
    FROM vendor_accounts
    WHERE canonical_vendor = 'CAL RED TECHNICAL CONSULTING'
      AND notes ILIKE '%NOT a T4 employee%'
      AND default_gl_code = '5210';

    IF vendor_note_count <> 1 THEN
        RAISE EXCEPTION
            'Expected the CAL RED vendor record to carry the non-T4 note, found %',
            vendor_note_count;
    END IF;
END
$$;

COMMIT;
