-- Final pass on the 44-row client-deposit credit group (account 8314462):
-- the Michael Richard (1 row) and "Barb Peacock" (8 rows) credits were
-- initially left out of the client-deposit-matching batches since neither
-- matches any `clients` record (they are confirmed employees). Per user
-- instruction, the SAME rules already applied to their other transactions
-- earlier this session apply here too:
--   Michael Richard -> DRIVER_PAY_REIMBURSEMENT (same as his "Bank Fees"
--     debit rows fixed earlier).
--   Barbara "Barb" Peacock -> business_personal = 'Personal' (same as her 2
--     excluded "Bank Fees" debit rows earlier), category is NOT changed to
--     DRIVER_PAY_REIMBURSEMENT here, consistent with the earlier decision to
--     exclude her rows from that reclassification and instead flag them
--     Personal.

BEGIN;

INSERT INTO backup_driver_advance_reclass_20260918
SELECT * FROM banking_transactions
WHERE transaction_id IN (36064,35565,35456,35338,35333,35335,35326,35248,35238,35235)
AND transaction_id NOT IN (SELECT transaction_id FROM backup_driver_advance_reclass_20260918);

-- Michael Richard: 1 row -> DRIVER_PAY_REIMBURSEMENT
UPDATE banking_transactions
SET category = 'DRIVER_PAY_REIMBURSEMENT'
WHERE transaction_id = 36064
AND category = 'Unclassified';

-- Barbara Peacock: 8 rows -> business_personal = 'Personal' (category unchanged)
UPDATE banking_transactions
SET business_personal = 'Personal'
WHERE transaction_id IN (35565,35456,35338,35333,35335,35326,35248,35238,35235);

COMMIT;
