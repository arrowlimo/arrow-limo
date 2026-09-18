-- =====================================================================
-- Correct GL miscoding: Jack Carter GL 2210 receipts are vehicle lease
-- payments (GL 5150), not driver wages
-- =====================================================================
-- Context: user confirmed Jack Carter is not a driver-wage vendor for
-- these two receipts; they were miscoded to GL 2210 (Driver Wages &
-- Reimbursements) and should be GL 5150 (Vehicle Lease Payments) like
-- all other Jack Carter transactions, linked to vehicle L-8 (vehicle_id=6).
--   171246  2013-05-22  $885.65   'CHQ 184 JACK CARTER'  GL 2210 -> 5150
--   221952  2013-01-21  $1,920.65 'JACK CARTER'          GL 2210 -> 5150
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS backup_jack_carter_gl2210_correction_20260918_receipts AS
SELECT * FROM receipts WHERE receipt_id IN (171246, 221952);

DO $$
DECLARE
    v_count integer;
BEGIN
    SELECT count(*) INTO v_count FROM receipts
    WHERE receipt_id IN (171246, 221952) AND gl_account_code = '2210';
    IF v_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 receipts on GL 2210, found %', v_count;
    END IF;
END $$;

UPDATE receipts
SET gl_account_code = '5150',
    gl_code = '5150',
    gl_account_name = 'Vehicle Lease Payments',
    vehicle_id = 6,
    vehicle_number = 'L-8',
    comment = COALESCE(comment || ' | ', '') || 'Reclassified 2026-09-18: was miscoded as Driver Wages (2210); this is a Jack Carter vehicle lease payment for L-8, not driver pay',
    updated_at = now()
WHERE receipt_id IN (171246, 221952);

DO $$
DECLARE
    v_count integer;
BEGIN
    SELECT count(*) INTO v_count FROM receipts
    WHERE receipt_id IN (171246, 221952) AND gl_account_code = '5150' AND vehicle_id = 6;
    IF v_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 receipts reclassified to GL 5150 / vehicle L-8, found %', v_count;
    END IF;
END $$;

COMMIT;
