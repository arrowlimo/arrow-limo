-- Fix Liquor Barn receipt 221589/221590 (split_group_id 221588, 2013-02-01,
-- $70.26 total) which was miscoded during the 2026-07-15 split-creation pass.
--
-- ROOT CAUSE: both split lines had gl_account_code set to a BANK/CASH ASSET
-- ACCOUNT (1011 = CIBC Checking 0228362, 1015 = Petty Cash) instead of the
-- actual expense category. This is what made the receipt display as
-- "SPLIT (2 lines) — 1011 — CIBC Checking 0228362" in the GL/Category column
-- and look like it involved a banking asset transfer, when in reality this
-- is an ordinary client-amenities (beverage) purchase like every other
-- Liquor Barn receipt in the system (all ~30 others are coded 5116, single
-- line, mostly no banking link).
--
-- Evidence this was a one-off data-entry error, not an intentional pattern:
--   - GL 1011 (CIBC Checking 0228362) is used on exactly ONE receipt system-
--     wide: this one.
--   - GL 1015 (Petty Cash) is used correctly on 1782 legitimate "PETTY CASH
--     FUNDING" transfer receipts, but this is the ONLY one of those 1783
--     rows flagged is_split_receipt = TRUE — i.e. the only case where Petty
--     Cash was used as a split line on a vendor purchase rather than an
--     actual cash-box funding transfer.
--   - The $60.00 portion (receipt 221589) is linked to real banking
--     transaction 77824 (Scotia acct 903990106011, 2013-02-01, "Liquor
--     Barn", debit $60.00) — a completely different bank than the GL code
--     (1011 = CIBC) implied, confirming the GL code was never meant to
--     describe the bank account, it was simply wrong.
--
-- FIX: recode both split lines to 5116 "Client Amenities - Food, Coffee,
-- Supplies" (matching how every other Liquor Barn receipt is coded).
-- Payment method and the real banking_transaction_id link are left as-is
-- since those correctly reflect that $60 was paid by debit card (matched to
-- a real bank transaction) and $10.26 was paid in cash.

UPDATE receipts
SET gl_account_code = '5116'
WHERE receipt_id IN (221589, 221590)
  AND gl_account_code IN ('1011', '1015');

UPDATE receipt_gl_splits
SET gl_code = '5116',
    gl_account_code = '5116'
WHERE receipt_id IN (221589, 221590)
  AND gl_code IN ('1011', '1015');
