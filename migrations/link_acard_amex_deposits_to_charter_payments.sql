-- Link unreconciled ACARD (American Express merchant) bank deposits to their
-- source charter_payments rows.
--
-- Context: VCARD/MCARD/DCARD merchant deposits were already linked to
-- charter_payments (via banking_transaction_id) by a prior reconciliation
-- pass (source='PAYMENTS_TABLE_REBUILD_20260417' and related batches), using
-- an exact face-value amount match. ACARD (Amex) deposits were never
-- reconciled by that pass: exact amount matching against charter_payments
-- finds zero candidates because Amex settled net of its merchant discount
-- rate, not at face value.
--
-- Analysis performed: comparing 105 unlinked ACARD deposits (2012-01 through
-- 2014-06, CIBC/Scotia accounts) against unlinked charter_payments
-- (payment_method IN ('credit_card','unknown'), banking_transaction_id NULL)
-- confirms a consistent implied Amex discount rate of 3.5% (deposit = charge
-- amount * (1 - 0.035)). Requiring an exact reverse-fee match (charge amount
-- within $0.03 of deposit/0.965) within a realistic settlement window
-- (charge date 0-10 days before, up to 2 days after the deposit date) yields
-- 33 candidate pairs. Of those, charter_payment id 45966 (charter 4625,
-- $250.00) matches two different ACARD deposits equally well and is
-- therefore ambiguous -- it and both of its candidate deposits are EXCLUDED
-- from this migration and left for manual review.
--
-- This migration links only the 31 unambiguous, unique 1:1 matches.
-- The remaining ~74 ACARD deposits (8 ambiguous + 64 with no confident
-- candidate at the 3.5% rate) are NOT touched here and remain unlinked,
-- pending manual review.

BEGIN;

-- Snapshot affected charter_payments rows before change, for full revertibility.
CREATE TABLE IF NOT EXISTS backup_acard_linkage_20260918 AS
SELECT * FROM charter_payments WHERE 1=0;

INSERT INTO backup_acard_linkage_20260918
SELECT * FROM charter_payments
WHERE id IN (
  45910, 45915, 45988, 58229, 45970, 45960, 45974, 46025, 58551, 46061,
  58263, 46214, 46247, 46351, 46626, 58689, 46967, 47026, 58480, 58498,
  47305, 47384, 47441, 47579, 48090, 48091, 48767, 48860, 49514, 49650,
  49816
);

-- Apply the 31 verified (cp_id, banking_transaction_id) pairs.
-- Guard: only update rows still unlinked (banking_transaction_id IS NULL),
-- so this migration is safe to re-run without double-applying.
UPDATE charter_payments cp
SET banking_transaction_id = v.txid
FROM (VALUES
  (45910, 101831),
  (45915, 81409),
  (45988, 101912),
  (58229, 101915),
  (45970, 81577),
  (45960, 101942),
  (45974, 101948),
  (46025, 101988),
  (58551, 102007),
  (46061, 102021),
  (58263, 81789),
  (46214, 102045),
  (46247, 82012),
  (46351, 102101),
  (46626, 102152),
  (58689, 69530),
  (46967, 69569),
  (47026, 82411),
  (58480, 69731),
  (58498, 69741),
  (47305, 77799),
  (47384, 77862),
  (47441, 77903),
  (47579, 78058),
  (48090, 78522),
  (48091, 78523),
  (48767, 79202),
  (48860, 79265),
  (49514, 79947),
  (49650, 80130),
  (49816, 80276)
) AS v(cp_id, txid)
WHERE cp.id = v.cp_id
  AND cp.banking_transaction_id IS NULL;

COMMIT;
