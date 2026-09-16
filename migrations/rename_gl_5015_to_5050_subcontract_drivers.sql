-- Renumber/rename the newly-created contract-driver GL account from 5015
-- to 5050 "Subcontract Drivers" per owner direction (a cleaner code that
-- doesn't crowd immediately next to 5010 Driver Wages). Since 5015 was
-- created moments ago and is only referenced by the 4 Cal Red Technical
-- Consulting receipts and its vendor_accounts default GL code, this is a
-- safe in-place rename rather than leaving two near-duplicate accounts.

BEGIN;

DO $$
DECLARE
    existing_5050_count integer;
    receipts_on_5015 integer;
BEGIN
    SELECT COUNT(*) INTO existing_5050_count
    FROM chart_of_accounts WHERE account_code = '5050';

    IF existing_5050_count <> 0 THEN
        RAISE EXCEPTION 'GL 5050 already exists; aborting rename';
    END IF;

    SELECT COUNT(*) INTO receipts_on_5015
    FROM receipts WHERE gl_account_code = '5015';

    IF receipts_on_5015 <> 4 THEN
        RAISE EXCEPTION
            'Expected 4 receipts on GL 5015 before rename, found %',
            receipts_on_5015;
    END IF;
END
$$;

UPDATE chart_of_accounts
SET account_code = '5050',
    account_name = 'Subcontract Drivers',
    updated_at = CURRENT_TIMESTAMP
WHERE account_code = '5015';

UPDATE receipts
SET gl_account_code = '5050',
    gl_account_name = 'Subcontract Drivers',
    gl_code = '5050',
    gl_description = 'Subcontract Drivers',
    expense_account = '5050',
    category = 'Subcontract Drivers',
    updated_at = CURRENT_TIMESTAMP
WHERE gl_account_code = '5015';

UPDATE vendor_accounts
SET default_gl_code = '5050'
WHERE default_gl_code = '5015';

DO $$
DECLARE
    old_code_remaining integer;
    new_code_account integer;
    new_code_receipts integer;
BEGIN
    SELECT COUNT(*) INTO old_code_remaining
    FROM chart_of_accounts WHERE account_code = '5015';
    IF old_code_remaining <> 0 THEN
        RAISE EXCEPTION 'GL 5015 should no longer exist, found %', old_code_remaining;
    END IF;

    SELECT COUNT(*) INTO new_code_account
    FROM chart_of_accounts
    WHERE account_code = '5050' AND account_name = 'Subcontract Drivers';
    IF new_code_account <> 1 THEN
        RAISE EXCEPTION 'Expected exactly one GL 5050 account, found %', new_code_account;
    END IF;

    SELECT COUNT(*) INTO new_code_receipts
    FROM receipts WHERE gl_account_code = '5050';
    IF new_code_receipts <> 4 THEN
        RAISE EXCEPTION 'Expected 4 receipts on GL 5050, found %', new_code_receipts;
    END IF;
END
$$;

COMMIT;
