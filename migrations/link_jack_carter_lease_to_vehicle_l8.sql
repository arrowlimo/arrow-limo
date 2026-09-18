-- =====================================================================
-- Link Jack Carter vehicle lease/loan receipts to vehicle L-8
-- =====================================================================
-- Context: user confirmed the Jack Carter loan is for vehicle L-8
-- (2008 Ford Expedition, vehicle_id=6). Receipt 220944 already contains
-- an explicit reference "AUTO LEASE L08136 JACK CARTER" corroborating
-- this. None of the 27 Jack Carter loan/lease/NSF receipts previously
-- had vehicle_id populated.
--
-- Only the 25 GL 5150 (Vehicle Lease Payments) receipts are linked here.
-- Two receipts (221952 "JACK CARTER" $1,920.65 GL 2210 with description
-- '498785', and 171246 "CHQ 184 JACK CARTER" $885.65 GL 2210 "DEPOSIT
-- CHQ 184") are GL 2210 Driver Wages & Reimbursements - a different
-- transaction type (likely driver pay to the same person, not the
-- vehicle lease) - these are intentionally excluded from this vehicle
-- link and left for separate review if needed.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS backup_jack_carter_vehicle_link_20260918_receipts AS
SELECT * FROM receipts
WHERE (vendor_name ILIKE '%JACK CARTER%' OR description ILIKE '%JACK CARTER%')
  AND gl_account_code = '5150';

DO $$
DECLARE
    v_count integer;
BEGIN
    SELECT count(*) INTO v_count FROM vehicles WHERE vehicle_id = 6 AND vehicle_number = 'L-8';
    IF v_count <> 1 THEN
        RAISE EXCEPTION 'Expected vehicle_id=6 to be L-8, found % matching rows', v_count;
    END IF;
END $$;

UPDATE receipts
SET vehicle_id = 6,
    vehicle_number = 'L-8',
    comment = COALESCE(comment || ' | ', '') || 'Linked 2026-09-18: Jack Carter vehicle lease/loan confirmed for L-8 (2008 Ford Expedition)',
    updated_at = now()
WHERE (vendor_name ILIKE '%JACK CARTER%' OR description ILIKE '%JACK CARTER%')
  AND gl_account_code = '5150';

DO $$
DECLARE
    v_count integer;
BEGIN
    SELECT count(*) INTO v_count FROM receipts
    WHERE (vendor_name ILIKE '%JACK CARTER%' OR description ILIKE '%JACK CARTER%')
      AND gl_account_code = '5150'
      AND vehicle_id = 6;
    IF v_count < 20 THEN
        RAISE EXCEPTION 'Expected at least 20 Jack Carter GL 5150 receipts linked to vehicle_id 6, found %', v_count;
    END IF;
END $$;

COMMIT;
