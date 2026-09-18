-- =====================================================================
-- Flag unresolved Jack Carter (L-8) lease payment gaps and possible
-- catch-up candidates for manual review
-- =====================================================================
-- Context: monthly lease payment verification found 6 months where the
-- scheduled $1,885.65 Jack Carter lease payment was NSF'd and no
-- subsequent successful payment for that month is evident:
--   2012-01, 2012-02, 2012-09, 2012-10, 2013-03, 2013-07
--
-- 3 "extra" payment events exist that occur close to these gaps and
-- may be intended catch-ups, but the amounts do not cleanly reconcile
-- 1:1 against any specific gap month, so they are NOT being matched
-- automatically - flagged only as candidates for manual review:
--   2012-07-23  $1,885.65 (CHQ 9, receipt 140471)   - extra vs regular monthly cadence
--   2012-12-17  $1,885.65 (receipt 140934)           - extra vs regular monthly cadence
--   2013-05-01  $   889.87 (receipt 139631)           - partial, non-standard amount
--   2013-05-22  $   885.65 (CHQ 184, receipt 171246)  - partial, non-standard amount
--
-- This migration only adds review-flag metadata; it does not create,
-- delete, or reclassify any financial amounts.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS backup_jack_carter_lease_review_flags_20260918_receipts AS
SELECT * FROM receipts
WHERE receipt_id IN (
    -- unresolved NSF gap months (no matching successful payment found)
    217823, 217851, 220945, 220949,
    -- plus the two previously-missing NSF receipts newly created for Sep/Oct 2012
    (SELECT receipt_id FROM receipts WHERE banking_transaction_id = 102285 LIMIT 1),
    (SELECT receipt_id FROM receipts WHERE banking_transaction_id = 102316 LIMIT 1),
    -- candidate catch-up / extra payments
    140471, 140934, 139631, 171246
);

UPDATE receipts
SET validation_status = 'LEASE_PAYMENT_GAP_UNRESOLVED',
    comment = COALESCE(comment || ' | ', '') || 'Flagged 2026-09-18: Jack Carter L-8 lease payment audit - this month''s NSF has no subsequent successful payment on record; needs manual review to confirm if/when it was made up'
WHERE receipt_id IN (217823, 217851, 220945, 220949)
   OR banking_transaction_id IN (102285, 102316);

UPDATE receipts
SET comment = COALESCE(comment || ' | ', '') || 'Flagged 2026-09-18: Jack Carter L-8 lease payment audit - possible catch-up payment for an earlier NSF gap month; amount does not cleanly match a specific missed month, needs manual confirmation'
WHERE receipt_id IN (140471, 140934, 139631, 171246);

DO $$
DECLARE
    v_count integer;
BEGIN
    SELECT count(*) INTO v_count FROM receipts
    WHERE validation_status = 'LEASE_PAYMENT_GAP_UNRESOLVED'
      AND (vendor_name ILIKE '%JACK CARTER%' OR description ILIKE '%JACK CARTER%');
    IF v_count <> 6 THEN
        RAISE EXCEPTION 'Expected 6 Jack Carter receipts flagged as unresolved gap, found %', v_count;
    END IF;
END $$;

COMMIT;
