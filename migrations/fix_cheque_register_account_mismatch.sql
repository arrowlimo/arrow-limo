-- Fix cheque_register.account_number to match the account_number of the
-- banking_transaction it is actually linked to, for the 3 rows where
-- account_number was simply NULL/blank (safe, unambiguous backfill — no
-- competing cheque_register row exists for these numbers in the target
-- account, so no risk of creating an in-account collision).
UPDATE cheque_register cr
SET account_number = bt.account_number
FROM banking_transactions bt
WHERE bt.transaction_id = cr.banking_transaction_id
  AND cr.account_number IS NULL
  AND cr.id IN (307, 308, 310);

-- Merge duplicate cheque #227 (Heffner Auto Finance, $2525.25):
--   - id 274 (account 1615, correct payee "HEFFNER AUTO FINANCE", correct
--     memo, but missing its banking_transaction_id link)
--   - id 280 (mislabeled account 0228362, payee "UNKNOWN", but correctly
--     linked to banking_transaction 99963 which is the real Heffner Auto
--     bank posting in account 1615 and already has receipt 217317 attached)
-- These are the same real-world cheque entered twice. Keep id 274 (the
-- properly-labeled row), attach the correct banking link to it, and remove
-- the redundant duplicate row 280.
UPDATE cheque_register
SET banking_transaction_id = 99963
WHERE id = 274 AND cheque_number = '227' AND banking_transaction_id IS NULL;

DELETE FROM cheque_register WHERE id = 280;

