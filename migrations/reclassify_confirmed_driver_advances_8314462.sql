-- Reclassify 20 mislabeled banking_transactions on account 8314462 (CIBC Vehicle
-- Loans) that the old accountant's CSV flagged as "1375 Driver Advances" but our
-- DB had bucketed under unrelated old/wrong categories ("Bank Fees" or old GL
-- code "2550" = Related Party - Repayments Out, a bucket meant for David
-- Richard's related-party repayments, not employee reimbursements).
--
-- Verification performed per user's 4-point framework before applying anything:
--  1. Driver advances = petty cash funding for charter-related expenses (fuel,
--     meals, supplies). The system's driver float tables (driver_floats,
--     driver_float_returns, driver_float_summary) are empty for this era
--     (2018-2022), so exact per-charter amount/date verification is not
--     possible from live data for these historical rows; recategorization
--     below relies on confirmed employee identity instead.
--  2. Old GL codes are fine as long as the new category is proper. Old code
--     '2550' turned out to be used almost entirely (82/97 non-Roney rows) for
--     "ETRANSFER DAVID RICHARD" (a genuine related-party repayment) -- Sam
--     Roney's 8 entries were incidentally lumped into the same code even
--     though she is an employee, not a related party. This is corrected here.
--  3. Mike Woodrow: verified NOT an employee/driver (absent from `employees`
--     and `drivers`). 82 historical receipts to Mike Woodrow total $62,882.03
--     over 2017-2026, virtually all GL-coded 5440 "Rent & Utilities" with
--     varying (non-recurring-fixed) amounts. Confirmed genuine rent; the 9
--     "RENT"-categorized rows are NOT touched by this migration.
--  4. ROGERS: verified this bank description refers to the telecom company,
--     not driver Jason Rogers. Old GL code 5650 groups 88 "ROGERS" entries
--     alongside 79 "TELUS" entries (both telecom billers) with no personal
--     amounts. The 4 "ROGERS"-tagged rows are NOT touched by this migration.
--
-- Confirmed-employee reclassification (this migration):
--   Sam Roney       (employees.employee_id=132, driver/host-dispatcher)  - 10 rows
--   Michael Richard (employees.employee_id=9,  driver/chauffeur)         -  4 rows
--   Barbara Peacock (employees.employee_id=122, driver/chauffeur)        -  5 rows
--   John McLean     (employees.employee_id=119, driver/chauffeur)       -  1 row
-- Total: 20 rows -> recategorized to 'DRIVER_PAY_REIMBURSEMENT', matching the
-- existing category convention already used elsewhere in this account
-- (e.g. Bill Gagne, correction_2of3_add_8314462_20180904_billgagne.sql).
--
-- Explicitly NOT touched, left as "Bank Fees" pending further review because
-- identity could not be confirmed as an employee/driver:
--   Michelle Ferris (1 row, $100.00, 2019-04-08) - name not found in `employees`.
--   3 unnamed "INTERNET TRANSFER 000000xxxxxx" rows ($450, $100, $600) - no
--     payee name recorded at all, cannot attribute to any driver.
--
-- Note: two of accountant's CSV lines (John McLean, $50.00, 2021-03-12) point
-- to the SAME single bank transaction (35371) -- an apparent duplicate entry
-- in the accountant's source CSV, not a duplicate bank transaction. Only one
-- DB row is corrected.

BEGIN;

CREATE TABLE IF NOT EXISTS backup_driver_advance_reclass_20260918 AS
SELECT * FROM banking_transactions WHERE 1=0;

INSERT INTO backup_driver_advance_reclass_20260918
SELECT * FROM banking_transactions
WHERE transaction_id IN (
  35812,36106,35851,35293,35309,35232,35339,35371,35837,35274,35275,35416,
  35632,35852,35858,35659,35655,35792,35844,35723
);

UPDATE banking_transactions
SET category = 'DRIVER_PAY_REIMBURSEMENT'
WHERE transaction_id IN (
  35812,36106,35851,35293,35309,35232,35339,35371,35837,35274,35275,35416,
  35632,35852,35858,35659,35655,35792,35844,35723
)
AND category IN ('Bank Fees','2550');

COMMIT;
