-- Third pass on the 44-row client-deposit credit group (account 8314462):
-- user directly confirmed (owner authority/recognition) that the remaining 9
-- previously-unmatched names ARE clients, despite no exact match being found
-- in the `clients` table (likely due to name variants, maiden names, or
-- clients never fully entered into that table). Marked as 'Charter Income'
-- per the same established convention used for the prior two batches.
--
-- Rows (user-confirmed as clients):
--   36151 LINDA SIMMELINK      $200.00  2018-09-25
--   35888 KOLBY LUKAN          $700.00  2019-07-22
--   35827 BARRY A WARD         $75.00   2019-09-17
--   35824 1059684 ALBERTA LTD. $100.00  2019-09-19
--   35701 JESSE RUTHERFORD     $970.00  2019-12-23
--   35483 RYLEY J KRAUSE       $100.00  2020-08-04
--   35453 billi jo hickey      $112.00  2020-10-08
--   35450 SHENA BAUER          $205.00  2020-10-13
--   35447 MR RICK MEYN         $533.40  2020-10-16
--
-- Note: 35450 (SHENA BAUER) and 35483 (RYLEY J KRAUSE) were previously
-- excluded from the exact-amount-match batch (link_client_edeposits_8314462.sql)
-- because the only same-amount/date `payments` candidate belonged to a
-- different client (name mismatch) -- that exclusion concerned linking to a
-- SPECIFIC payment record, which still stands (no payments/charter_payments
-- row is linked here). This migration only corrects the banking_transaction
-- category label to reflect that the deposit itself is a genuine charter
-- client payment, per user confirmation.
--
-- Not included in this batch (per prior instruction, confirmed employees,
-- not clients): Michael Richard (36064, $100.00) and Barb Peacock (8 rows).

BEGIN;

INSERT INTO backup_driver_advance_reclass_20260918
SELECT * FROM banking_transactions
WHERE transaction_id IN (36151,35888,35827,35824,35701,35483,35453,35450,35447)
AND transaction_id NOT IN (SELECT transaction_id FROM backup_driver_advance_reclass_20260918);

UPDATE banking_transactions
SET category = 'Charter Income'
WHERE transaction_id IN (36151,35888,35827,35824,35701,35483,35453,35450,35447)
AND category = 'Unclassified';

COMMIT;
