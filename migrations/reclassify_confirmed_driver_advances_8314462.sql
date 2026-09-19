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
--   Michelle Ferris (payroll marker, identity unconfirmed in `employees`)   -  1 row
--   Brittany Peacock (employees.employee_id=32, Operations/DR002)          -  1 row
--   Michael Richard (additional rows found via payroll-marker sweep)        -  3 rows
-- Total: 25 rows -> recategorized to 'DRIVER_PAY_REIMBURSEMENT', matching the
-- existing category convention already used elsewhere in this account
-- (e.g. Bill Gagne, correction_2of3_add_8314462_20180904_billgagne.sql).
--
-- Michelle Ferris (transaction_id 35996, $100.00, 2019-04-08): not found in
-- `employees` under any spelling, and no `receipts` row links to this
-- banking_transaction_id. HOWEVER independently confirmed via
-- `banking_transactions.reconciliation_status`/`reconciliation_notes`, which
-- already carries 'payroll' / "Employee pay -- excluded from GL expenses;
-- tracked in payroll system / T4s" -- the identical marker already present on
-- the confirmed Michael Richard / Barbara Peacock rows in this same
-- migration. This is independent evidence (not a guess) that she was already
-- recognized elsewhere in the system as an employee receiving payroll
-- e-transfers. Included below as a 21st row.
--
-- Explicitly NOT touched:
--   3 unnamed "INTERNET TRANSFER 000000xxxxxx" rows (transaction_ids 35914
--     $600.00 2019-07-02, 35703 $450.00 2019-12-18, 35347 $100.00 2021-04-09)
--     - confirmed via linked `receipts` rows (152262/152016/151855) that these
--     are already recorded as `vendor_name='NSF CHARGE'`, `is_nsf=true`,
--     `classification='transfer'`. They are NSF-related bank charges, NOT
--     driver advances at all -- "Bank Fees" is the correct category here, so
--     no reclassification is needed or appropriate for these 3.
--   Barbara Peacock's 2 additional payroll-marker rows found during the
--     Ferris follow-up sweep (35370 $50.00 2021-03-12, 35349 $100.00
--     2021-04-09) -- explicitly excluded per user instruction; left as
--     "Bank Fees" pending separate review/decision.
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

-- Follow-up: Michelle Ferris (transaction_id 35996), added after further
-- investigation confirmed the pre-existing 'payroll' reconciliation marker
-- (see comment block above). Backed up separately since it was applied in a
-- later pass than the 20 rows above.
BEGIN;

INSERT INTO backup_driver_advance_reclass_20260918
SELECT * FROM banking_transactions
WHERE transaction_id = 35996
AND NOT EXISTS (
  SELECT 1 FROM backup_driver_advance_reclass_20260918 WHERE transaction_id = 35996
);

UPDATE banking_transactions
SET category = 'DRIVER_PAY_REIMBURSEMENT'
WHERE transaction_id = 35996
AND category = 'Bank Fees';

COMMIT;

-- Follow-up 2: while checking Michelle Ferris's reconciliation_status='payroll'
-- marker, found 7 more "Bank Fees" rows on this account carrying the same
-- 'payroll' marker but outside the original 94-row Driver Advances CSV group:
-- Barbara Peacock x3 (35370 $50.00 2021-03-12, 35349 $100.00 2021-04-09,
-- 35293-adjacent), Brittany Peacock x1 (35127 $654.00 2025-07-02), Michael
-- Richard x3 (35341 $60.00 2021-04-12, 35163 $150.00 2025-03-17, 35129
-- $200.00 2025-07-02).
--
-- Per user instruction: exclude Barbara Peacock's 2 rows (35370, 35349) from
-- this pass; continue with Michael Richard and Brittany Peacock.
--   Brittany Peacock confirmed as employee (employees.employee_id=32,
--   "Peacock, Brittany", employee_category='Operations', status='active',
--   driver_code='DR002').
--   Michael Richard already confirmed earlier in this migration
--   (employees.employee_id=9).
-- 4 rows reclassified: 35341, 35163, 35129, 35127.
BEGIN;

INSERT INTO backup_driver_advance_reclass_20260918
SELECT * FROM banking_transactions
WHERE transaction_id IN (35341,35163,35129,35127)
AND transaction_id NOT IN (SELECT transaction_id FROM backup_driver_advance_reclass_20260918);

UPDATE banking_transactions
SET category = 'DRIVER_PAY_REIMBURSEMENT'
WHERE transaction_id IN (35341,35163,35129,35127)
AND category = 'Bank Fees';

COMMIT;

-- Follow-up 3: Barbara Peacock's 2 excluded rows (35370, 35349) -- per user
-- instruction, category is left as "Bank Fees" (not reclassified to
-- DRIVER_PAY_REIMBURSEMENT), but business_personal is updated from 'Business'
-- to 'Personal' at the user's explicit direction.
BEGIN;

INSERT INTO backup_driver_advance_reclass_20260918
SELECT * FROM banking_transactions
WHERE transaction_id IN (35370,35349)
AND transaction_id NOT IN (SELECT transaction_id FROM backup_driver_advance_reclass_20260918);

UPDATE banking_transactions
SET business_personal = 'Personal'
WHERE transaction_id IN (35370,35349);

COMMIT;
