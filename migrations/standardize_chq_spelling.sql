-- Standardize "CHO ###" (OCR/typo for CHQ) and spelled-out "Cheque ###" to the
-- established "CHQ ###" convention used by ~99% of all cheque-number
-- references across cheque_register, receipts, and banking_transactions.
--
-- Scope discipline: only rows that reference a SPECIFIC numbered cheque are
-- touched. Generic bank-statement wording where "cheque" is just the normal
-- English word for a check/payment instrument (e.g. "NSF Returned Cheque",
-- "Cheque order charge", "Custom Cheques", "CHEQUE 75770399 5" pre-authorized
-- debit references) is left untouched — that is authentic historical bank
-- statement text, not a typo of our internal "CHQ ###" labeling convention.

-- 1) banking_transactions: OCR-style "CHO ###" -> "CHQ ###"
--    (same "verified_2013_2014_scotia" import batch, same account, same
--    week as dozens of sibling rows that correctly say "CHQ ###")
UPDATE banking_transactions
SET description = REPLACE(description, 'CHO 212', 'CHQ 212')
WHERE transaction_id = 78630;

UPDATE banking_transactions
SET description = REPLACE(description, 'CHO 218', 'CHQ 218')
WHERE transaction_id = 78678;

UPDATE banking_transactions
SET description = REPLACE(description, 'CHO 219', 'CHQ 219')
WHERE transaction_id = 78711;

-- Backfill check_number on the two CHO rows that were missing it, matching
-- the pattern already used by every sibling row in the same batch.
UPDATE banking_transactions SET check_number = '212' WHERE transaction_id = 78630 AND check_number IS NULL;
UPDATE banking_transactions SET check_number = '218' WHERE transaction_id = 78678 AND check_number IS NULL;

-- 2) banking_transactions: the one spelled-out "Cheque 274 Tammy Petitit"
--    inside the same verified Scotia import batch where every other cheque
--    reference uses "CHQ ###".
UPDATE banking_transactions
SET description = 'CHQ 274 TAMMY PETITIT'
WHERE transaction_id = 79285 AND description = 'Cheque 274 Tammy Petitit';

-- 3) receipts.vendor_name: CHO -> CHQ
UPDATE receipts SET vendor_name = 'CHQ 218' WHERE receipt_id = 139772 AND vendor_name = 'CHO 218';

-- 4) receipts: spelled-out "CHEQUE #NNN" -> "CHQ NNN" to match each
--    receipt's own description field, which already uses the correct
--    convention (e.g. description already says "CHQ 203").
UPDATE receipts SET vendor_name = 'CHQ 203' WHERE receipt_id = 218219 AND vendor_name = 'CHEQUE #203';
UPDATE receipts SET vendor_name = 'CHQ 365 SHAWN CALLIN' WHERE receipt_id = 218238 AND vendor_name = 'CHEQUE #365';
UPDATE receipts SET vendor_name = 'CHQ 361 SHAWN CALLIN' WHERE receipt_id = 218285 AND vendor_name = 'CHEQUE #361';

UPDATE receipts
SET vendor_name = 'CHQ 274 TAMMY PETITIT', description = 'CHQ 274 Tammy Petitit'
WHERE receipt_id = 171472 AND vendor_name = 'CHEQUE 274 TAMMY PETITIT';

-- 5) receipts: remove redundant duplicated "- Cheque 263" wording, keep the
--    single correct "CHQ 263" reference.
UPDATE receipts
SET description = 'CHQ 263 000000017571366'
WHERE receipt_id = 221553 AND description = 'CHQ 263 - Cheque 263 000000017571366';
