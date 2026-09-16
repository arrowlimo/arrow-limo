-- Gordon Deans / CAL RED TECHNICAL CONSULTING is a non-T4 subcontractor
-- (a vendor paid through his own corporation), not a T4 employee. GL 5210
-- ("Driver Wages & Reimbursements") sits under the 5200 "Labor Expenses"
-- header alongside CPP/EI/WCB/benefits accounts - i.e. it is an
-- employee-payroll bucket and is not the correct GL for subcontracted
-- driving services. This migration creates a new postable GL account,
-- 5015 "Contract Driver Services (Subcontractors)", as a COGS account
-- parallel to 5010 "Driver Wages" (both roll up under 5000 as the direct
-- cost of driving revenue-generating charters), but explicitly for
-- non-employee subcontracted driver pay, and moves all 4 Cal Red receipts
-- from 5210 to the new 5015 code.

BEGIN;

INSERT INTO chart_of_accounts (
    account_code,
    parent_account,
    account_name,
    account_type,
    description,
    is_active,
    account_level,
    is_header_account,
    normal_balance,
    is_business_expense,
    is_linked_account,
    is_tax_applicable,
    requires_employee,
    requires_vehicle
)
VALUES (
    '5015',
    '5000',
    'Contract Driver Services (Subcontractors)',
    'COGS',
    'Driving services paid to non-employee subcontractors invoicing '
        || 'through their own corporation/business (e.g. Cal Red Technical '
        || 'Consulting). Distinct from GL 5010 Driver Wages and GL 5210 '
        || 'Driver Wages & Reimbursements, which are for T4 employees. No '
        || 'CPP/EI/tax withholding applies to this account; no T4 is '
        || 'issued for amounts recorded here.',
    TRUE,
    0,
    FALSE,
    'DEBIT',
    TRUE,
    FALSE,
    FALSE,
    FALSE,
    FALSE
)
ON CONFLICT (account_code) DO NOTHING;

CREATE TEMP TABLE cal_red_gl_move (
    receipt_id bigint PRIMARY KEY
) ON COMMIT DROP;

INSERT INTO cal_red_gl_move (receipt_id)
SELECT receipt_id
FROM receipts
WHERE UPPER(TRIM(COALESCE(canonical_vendor, vendor_name)))
    = 'CAL RED TECHNICAL CONSULTING';

DO $$
DECLARE
    active_count integer;
BEGIN
    SELECT COUNT(*) INTO active_count FROM cal_red_gl_move;
    IF active_count <> 4 THEN
        RAISE EXCEPTION
            'Expected 4 CAL RED TECHNICAL CONSULTING receipts to move, found %',
            active_count;
    END IF;
END
$$;

UPDATE receipts receipt
SET gl_account_code = '5015',
    gl_account_name = account.account_name,
    gl_code = '5015',
    gl_description = account.account_name,
    expense_account = '5015',
    category = account.account_name,
    updated_at = CURRENT_TIMESTAMP
FROM cal_red_gl_move mapping
JOIN chart_of_accounts account
  ON account.account_code = '5015'
WHERE receipt.receipt_id = mapping.receipt_id;

UPDATE vendor_accounts
SET default_gl_code = '5015',
    default_category = 'subcontractor_driver_pay'
WHERE canonical_vendor = 'CAL RED TECHNICAL CONSULTING';

DO $$
DECLARE
    remaining_5210_count integer;
    moved_5015_count integer;
BEGIN
    SELECT COUNT(*)
    INTO remaining_5210_count
    FROM receipts
    WHERE UPPER(TRIM(COALESCE(canonical_vendor, vendor_name)))
        = 'CAL RED TECHNICAL CONSULTING'
      AND gl_account_code = '5210';

    IF remaining_5210_count <> 0 THEN
        RAISE EXCEPTION
            'Expected zero CAL RED receipts remaining on GL 5210, found %',
            remaining_5210_count;
    END IF;

    SELECT COUNT(*)
    INTO moved_5015_count
    FROM receipts
    WHERE UPPER(TRIM(COALESCE(canonical_vendor, vendor_name)))
        = 'CAL RED TECHNICAL CONSULTING'
      AND gl_account_code = '5015';

    IF moved_5015_count <> 4 THEN
        RAISE EXCEPTION
            'Expected 4 CAL RED receipts on GL 5015, found %',
            moved_5015_count;
    END IF;
END
$$;

COMMIT;
