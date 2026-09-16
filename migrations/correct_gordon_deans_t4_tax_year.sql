-- Gordon Deans' last year as a T4 employee was 2011. Starting in 2012 he
-- switched to invoicing Arrow Limo as a subcontractor through his own
-- corporation (CAL RED TECHNICAL CONSULTING). There is no supporting
-- payroll evidence in this system for a 2012 T4 (zero receipts, zero
-- driver_payroll rows tied to his employee_id for 2012), yet
-- employee_t4_records held a single T4 row tagged tax_year = 2012 (notes:
-- "From 2012 T4 PDF"). This was an accountant error: his company invoiced
-- Arrow Limo for his 2012 work as a subcontractor, so a 2012 T4 should
-- never have been issued/recorded for him at all. Left as-is, this made it
-- look like Arrow Limo paid Gordon Deans twice on paper for 2012: once as
-- T4 employment income and again as Cal Red subcontractor invoices. This
-- migration corrects the tax_year on that T4 record to 2011 (his actual
-- last T4 year) and logs the correction for audit purposes.

BEGIN;

DO $$
DECLARE
    mislabeled_2012_t4_count integer;
BEGIN
    SELECT COUNT(*)
    INTO mislabeled_2012_t4_count
    FROM employee_t4_records
    WHERE employee_id = 1979
      AND tax_year = 2012;

    IF mislabeled_2012_t4_count <> 1 THEN
        RAISE EXCEPTION
            'Expected exactly one mislabeled 2012 T4 record for employee '
            '1979 (Gordon Deans), found %',
            mislabeled_2012_t4_count;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS backup_gordon_deans_t4_year_correction_20260916 AS
SELECT *
FROM employee_t4_records
WHERE employee_id = 1979
  AND tax_year = 2012;

INSERT INTO t4_compliance_corrections (
    employee_id,
    tax_year,
    correction_type,
    correction_reason,
    original_t4_issued,
    original_employment_income,
    original_cpp_contributions,
    original_ei_contributions,
    original_income_tax,
    corrected_employment_income,
    corrected_cpp_contributions,
    corrected_ei_contributions,
    corrected_income_tax,
    income_variance,
    cpp_variance,
    ei_variance,
    tax_variance,
    correction_status,
    impacts_deferred_wages,
    prepared_by
)
SELECT
    t4.employee_id,
    2012,
    'tax_year_mislabel',
    'T4 record was tagged tax_year=2012 ("From 2012 T4 PDF") but this was '
        || 'an accountant error: Gordon Deans'' company (Cal Red Technical '
        || 'Consulting) invoiced Arrow Limo for his 2012 work as a '
        || 'subcontractor, so no 2012 T4 should have been issued/recorded. '
        || 'His last year as a T4 employee was 2011. No 2012 payroll/'
        || 'receipt evidence exists for him in this system as an employee. '
        || 'Corrected tax_year to 2011 to prevent double-reporting his '
        || '2012 income (once as T4 wages, once as Cal Red subcontractor '
        || 'invoices).',
    TRUE,
    t4.box_14_employment_income,
    t4.box_16_cpp_contributions,
    t4.box_18_ei_premiums,
    t4.box_22_income_tax,
    t4.box_14_employment_income,
    t4.box_16_cpp_contributions,
    t4.box_18_ei_premiums,
    t4.box_22_income_tax,
    0,
    0,
    0,
    0,
    'corrected',
    FALSE,
    NULL
FROM employee_t4_records t4
WHERE t4.employee_id = 1979
  AND t4.tax_year = 2012;

UPDATE employee_t4_records
SET tax_year = 2011,
    notes = COALESCE(notes || E'\n', '')
        || 'Corrected 2026-09-16: PDF was dated/filed in 2012 but reports '
        || 'tax year 2011 (Gordon Deans'' last year as a T4 employee); '
        || 'he switched to Cal Red Technical Consulting subcontractor '
        || 'invoicing for 2012 onward.',
    updated_at = CURRENT_TIMESTAMP
WHERE employee_id = 1979
  AND tax_year = 2012;

DO $$
DECLARE
    remaining_2012_t4_count integer;
    corrected_2011_t4_count integer;
    correction_log_count integer;
BEGIN
    SELECT COUNT(*)
    INTO remaining_2012_t4_count
    FROM employee_t4_records
    WHERE employee_id = 1979
      AND tax_year = 2012;

    IF remaining_2012_t4_count <> 0 THEN
        RAISE EXCEPTION
            'Expected zero remaining 2012 T4 records for employee 1979, '
            'found %',
            remaining_2012_t4_count;
    END IF;

    SELECT COUNT(*)
    INTO corrected_2011_t4_count
    FROM employee_t4_records
    WHERE employee_id = 1979
      AND tax_year = 2011;

    IF corrected_2011_t4_count <> 1 THEN
        RAISE EXCEPTION
            'Expected exactly one corrected 2011 T4 record for employee '
            '1979, found %',
            corrected_2011_t4_count;
    END IF;

    SELECT COUNT(*)
    INTO correction_log_count
    FROM t4_compliance_corrections
    WHERE employee_id = 1979
      AND tax_year = 2012
      AND correction_type = 'tax_year_mislabel';

    IF correction_log_count <> 1 THEN
        RAISE EXCEPTION
            'Expected exactly one logged T4 correction for employee 1979, '
            'found %',
            correction_log_count;
    END IF;
END
$$;

COMMIT;
