-- Repair bank account registry (2026-09-09)
--
-- Issues fixed:
--  1. Account 903990106011 (Scotiabank, historical 2011-2019) had 3,394 transactions
--     but was never registered in bank_accounts.
--  2. Those 3,394 Scotiabank transactions were linked to bank_id=2, which is
--     "CIBC Business Deposit" -- a wrong-institution linkage.
--  3. 23,861 of 32,988 banking_transactions had a NULL bank_id.
--  4. bank_accounts stored the legacy account as '74-61615' while
--     banking_transactions and cibc_accounts both use '1615', so
--     v_banking_transactions_with_aliases resolved no aliases for that account.
--
-- Canonical account number for the legacy CIBC account is standardized to '1615'
-- (the format actually stored in banking_transactions); '74-61615' is retained
-- as a QuickBooks alias.

BEGIN;

-- 1. Register the historical Scotiabank account (closed; no longer in use).
INSERT INTO bank_accounts (
    account_name, institution_name, account_number, account_type,
    currency, swift_code, is_active, closed_date, notes)
SELECT 'Scotiabank Business Checking (Historical)', 'Bank of Nova Scotia',
       '903990106011', 'checking', 'CAD', 'NOSCCATT', false, DATE '2019-10-29',
       'Historical Scotiabank account, txns 2011-12-14 to 2019-10-29. '
       'Registered 2026-09-09; previously unregistered and mis-linked to bank_id=2.'
WHERE NOT EXISTS (
    SELECT 1 FROM bank_accounts WHERE account_number = '903990106011');

-- 2. Standardize the legacy CIBC account number to match the transaction data.
UPDATE bank_accounts
   SET account_number = '1615',
       account_name   = 'CIBC Business Checking (Legacy 1615)',
       updated_at     = now()
 WHERE account_number = '74-61615';

-- 3. Repoint aliases at the corrected canonical value and keep the QB format.
UPDATE account_number_aliases
   SET canonical_account_number = '1615'
 WHERE canonical_account_number = '74-61615';

INSERT INTO account_number_aliases (
    statement_format, canonical_account_number, institution_name, account_type, notes)
SELECT '74-61615', '1615', 'CIBC', 'checking', 'QuickBooks hyphenated ref'
WHERE NOT EXISTS (
    SELECT 1 FROM account_number_aliases WHERE statement_format = '74-61615');

INSERT INTO account_number_aliases (
    statement_format, canonical_account_number, institution_name, account_type, notes)
SELECT v.sf, '903990106011', 'Scotiabank', 'checking',
       'Historical Scotiabank account (closed 2019)'
  FROM (VALUES ('903990106011'), ('6011'), ('903990 10600 11')) AS v(sf)
 WHERE NOT EXISTS (
    SELECT 1 FROM account_number_aliases a WHERE a.statement_format = v.sf);

-- 4. Rebuild every bank_id from account_number, correcting the mis-linked
--    Scotiabank rows and backfilling all NULLs.
UPDATE banking_transactions bt
   SET bank_id = ba.bank_id
  FROM bank_accounts ba
 WHERE ba.account_number = bt.account_number
   AND bt.bank_id IS DISTINCT FROM ba.bank_id;

COMMIT;

-- Verification: both queries must return 0.
-- SELECT count(*) FROM banking_transactions WHERE bank_id IS NULL;
-- SELECT count(*) FROM banking_transactions bt JOIN bank_accounts ba USING (bank_id)
--  WHERE ba.account_number <> bt.account_number;
