-- Second pass on the 44-row client-deposit credit group (account 8314462):
-- per user's revised instruction, match by CLIENT NAME ONLY (any amount, not
-- requiring an exact-amount payment candidate), then mark the bank
-- transaction as 'Charter Income' -- matching the established convention
-- already used for other client e-transfer deposits on this account (e.g.
-- NEW WEST ENTERTAINMENT, AMY KLEIN, both previously approved 'Charter
-- Income' entries).
--
-- Purpose (per user): this is solely to ensure charter revenue is not
-- double-counted / mislabeled as an anomaly -- NOT an attempt at exact
-- payment-to-deposit reconciliation. No specific `payments`/`charter_payments`
-- row is linked here since no exact-amount match exists; only the bank
-- transaction's category is corrected to reflect it as a genuine client
-- charter deposit.
--
-- Confirmed matches (verified against `clients.client_name`):
--   36076 Jerrica              $250.00  2019-01-07 -> Knickle Jerrica (1234)
--   36030 ELENA DUVAL          $620.00  2019-02-25 -> DuVal, Elena (4077)
--   35853 ERIK RICHARD         $100.00  2019-08-26 -> Richard, Erik (1727)
--   35790 CAMERON O'CONNELL    $136.00  2019-10-07 -> O'Connell, Cam (2184)
--   35781 MR. JUSTIN DOUGLAS   $722.63  2019-10-21 -> Vick, Justin (4279)
--         VICK
--   35774 LINDY BENNETT        $685.00  2019-10-28 -> Bennett, Lindy (2306)
--   35756 CARMEN LOMAS         $332.00  2019-11-12 -> Lomas, Carmen (4311)
--   35587 Caleb                $195.00  2020-02-18 -> Brettelle, Kaleb (4408)
--         (first-name-only match; "Caleb"/"Kaleb" spelling variant, no other
--         candidate client with that first name found)
--
-- No client match found (left "Unclassified", pending further investigation
-- in a later round):
--   LINDA SIMMELINK, KOLBY LUKAN, BARRY A WARD, 1059684 ALBERTA LTD.,
--   JESSE RUTHERFORD, RYLEY J KRAUSE, billi jo hickey, SHENA BAUER,
--   MR RICK MEYN.
-- Not a client at all (existing employees, not applicable to this batch):
--   Michael Richard (1 row) -- already a confirmed employee, not a client.
--   Barb Peacock (8 rows) -- confirmed employee (Barbara Peacock), no
--     matching client record found under "Peacock" at all.

BEGIN;

INSERT INTO backup_driver_advance_reclass_20260918
SELECT * FROM banking_transactions
WHERE transaction_id IN (36076,36030,35853,35790,35781,35774,35756,35587)
AND transaction_id NOT IN (SELECT transaction_id FROM backup_driver_advance_reclass_20260918);

UPDATE banking_transactions
SET category = 'Charter Income'
WHERE transaction_id IN (36076,36030,35853,35790,35781,35774,35756,35587)
AND category = 'Unclassified';

COMMIT;
