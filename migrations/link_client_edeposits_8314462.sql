-- Link 16 client e-transfer deposits on account 8314462 (CIBC Vehicle Loans)
-- to their already-recorded charter payments. These were part of the 44-row
-- "1375 Driver Advances" (accountant CSV) group flagged
-- NEEDS_REVIEW_NEVER_CATEGORIZED -- but all 44 turned out to be CREDITS
-- (money IN), the opposite direction of every driver-advance debit fixed
-- earlier this session. Per user direction, matched these against client
-- names and their related charters/payments instead.
--
-- Matching method: for each unlinked "Unclassified" credit, searched
-- `payments` for an e_transfer payment with the exact same amount, a payment
-- date within 30 days, and `banking_transaction_id IS NULL`. Where more than
-- one candidate existed at the same amount/window, disambiguated using the
-- charter's `clients.client_name` against the name in the bank description.
-- All 16 below have a clients.client_name match to the bank description's
-- payer name (exact or an obvious nickname/spelling variant).
--
-- Category is intentionally left as "Unclassified" on banking_transactions,
-- matching the established convention: 350 of the existing charter-linked
-- deposits on this account already use "Unclassified" as their category, with
-- the actual revenue recognition happening via `charter_payments`/`payments`
-- -> `income_ledger`, not via the bank transaction's category label.
--
-- Explicitly NOT linked / excluded from this batch:
--   35774 ($685.00, 2019-10-28, "LINDY BENNETT") - only same-amount/date
--     candidate found is payment_id 17531 for charter 13849, whose actual
--     client is "Kroetsch, Darcy" -- name mismatch, likely a coincidental
--     amount collision. Left unlinked.
--   35483 ($100.00, 2020-08-04, "RYLEY J KRAUSE") - only candidate is
--     payment_id 18162 for charter 14308, client "Hewitt, Brandi" -- name
--     mismatch. Left unlinked.
--   35450 ($205.00, 2020-10-13, "SHENA BAUER") - only candidate is payment_id
--     18295 for charter 14416, client "Barker, Asya" -- name mismatch. Left
--     unlinked.
--   35587 ($195.00, 2020-02-18, "Caleb") - only candidate is payment_id 17907
--     for charter 14128, client "Brettelle, Kaleb" -- plausible same-person
--     spelling/nickname match (Caleb/Kaleb) but only a first name given with
--     no surname in the bank description; too uncertain to link without
--     further confirmation. Left unlinked, flagged for review.
--   The remaining ~24 of the 44-row group had no same-amount e_transfer
--     payment candidate found within a 30-day window at all; left unlinked
--     pending further investigation.

BEGIN;

CREATE TABLE IF NOT EXISTS backup_client_deposit_link_20260918 AS
SELECT * FROM payments WHERE 1=0;

CREATE TABLE IF NOT EXISTS backup_client_deposit_link_charter_payments_20260918 AS
SELECT * FROM charter_payments WHERE 1=0;

INSERT INTO backup_client_deposit_link_20260918
SELECT * FROM payments WHERE payment_id IN (
  16804,17042,17171,17295,17347,17336,17337,17363,17770,17870,17871,18012,18169,18283,19116,19337
);

INSERT INTO backup_client_deposit_link_charter_payments_20260918
SELECT * FROM charter_payments WHERE id IN (
  63811,59407,60022,62868,62589,66613,62562,60516,63227,65436,65061,61025,63231,59570,63354,61874
);

-- transaction_id -> payment_id mapping:
-- 36031->16804, 35965->17042, 35908->17171, 35859->17295, 35842->17347,
-- 35843->17336, 35847->17337, 35838->17363, 35687->17770, 35607->17870,
-- 35603->17871, 35552->18012, 35487->18169, 35457->18283, 35264->19116,
-- 35244->19337

UPDATE payments SET banking_transaction_id = 36031 WHERE payment_id = 16804 AND banking_transaction_id IS NULL;
UPDATE payments SET banking_transaction_id = 35965 WHERE payment_id = 17042 AND banking_transaction_id IS NULL;
UPDATE payments SET banking_transaction_id = 35908 WHERE payment_id = 17171 AND banking_transaction_id IS NULL;
UPDATE payments SET banking_transaction_id = 35859 WHERE payment_id = 17295 AND banking_transaction_id IS NULL;
UPDATE payments SET banking_transaction_id = 35842 WHERE payment_id = 17347 AND banking_transaction_id IS NULL;
UPDATE payments SET banking_transaction_id = 35843 WHERE payment_id = 17336 AND banking_transaction_id IS NULL;
UPDATE payments SET banking_transaction_id = 35847 WHERE payment_id = 17337 AND banking_transaction_id IS NULL;
UPDATE payments SET banking_transaction_id = 35838 WHERE payment_id = 17363 AND banking_transaction_id IS NULL;
UPDATE payments SET banking_transaction_id = 35687 WHERE payment_id = 17770 AND banking_transaction_id IS NULL;
UPDATE payments SET banking_transaction_id = 35607 WHERE payment_id = 17870 AND banking_transaction_id IS NULL;
UPDATE payments SET banking_transaction_id = 35603 WHERE payment_id = 17871 AND banking_transaction_id IS NULL;
UPDATE payments SET banking_transaction_id = 35552 WHERE payment_id = 18012 AND banking_transaction_id IS NULL;
UPDATE payments SET banking_transaction_id = 35487 WHERE payment_id = 18169 AND banking_transaction_id IS NULL;
UPDATE payments SET banking_transaction_id = 35457 WHERE payment_id = 18283 AND banking_transaction_id IS NULL;
UPDATE payments SET banking_transaction_id = 35264 WHERE payment_id = 19116 AND banking_transaction_id IS NULL;
UPDATE payments SET banking_transaction_id = 35244 WHERE payment_id = 19337 AND banking_transaction_id IS NULL;

UPDATE charter_payments SET banking_transaction_id = 36031 WHERE id = 63811 AND banking_transaction_id IS NULL;
UPDATE charter_payments SET banking_transaction_id = 35965 WHERE id = 59407 AND banking_transaction_id IS NULL;
UPDATE charter_payments SET banking_transaction_id = 35908 WHERE id = 60022 AND banking_transaction_id IS NULL;
UPDATE charter_payments SET banking_transaction_id = 35859 WHERE id = 62868 AND banking_transaction_id IS NULL;
UPDATE charter_payments SET banking_transaction_id = 35842 WHERE id = 62589 AND banking_transaction_id IS NULL;
UPDATE charter_payments SET banking_transaction_id = 35843 WHERE id = 66613 AND banking_transaction_id IS NULL;
UPDATE charter_payments SET banking_transaction_id = 35847 WHERE id = 62562 AND banking_transaction_id IS NULL;
UPDATE charter_payments SET banking_transaction_id = 35838 WHERE id = 60516 AND banking_transaction_id IS NULL;
UPDATE charter_payments SET banking_transaction_id = 35687 WHERE id = 63227 AND banking_transaction_id IS NULL;
UPDATE charter_payments SET banking_transaction_id = 35607 WHERE id = 65436 AND banking_transaction_id IS NULL;
UPDATE charter_payments SET banking_transaction_id = 35603 WHERE id = 65061 AND banking_transaction_id IS NULL;
UPDATE charter_payments SET banking_transaction_id = 35552 WHERE id = 61025 AND banking_transaction_id IS NULL;
UPDATE charter_payments SET banking_transaction_id = 35487 WHERE id = 63231 AND banking_transaction_id IS NULL;
UPDATE charter_payments SET banking_transaction_id = 35457 WHERE id = 59570 AND banking_transaction_id IS NULL;
UPDATE charter_payments SET banking_transaction_id = 35264 WHERE id = 63354 AND banking_transaction_id IS NULL;
UPDATE charter_payments SET banking_transaction_id = 35244 WHERE id = 61874 AND banking_transaction_id IS NULL;

COMMIT;
