-- Keep fuel spending and liters synchronized from receipts into the dated
-- fuel log. Receipts without a vehicle are recorded under GENERAL.

ALTER TABLE vehicle_fuel_log
    ALTER COLUMN liters TYPE numeric(12,3);

WITH ranked AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY receipt_id
            ORDER BY id DESC
        ) AS row_number
    FROM vehicle_fuel_log
    WHERE receipt_id IS NOT NULL
)
DELETE FROM vehicle_fuel_log log
USING ranked
WHERE log.id = ranked.id
  AND ranked.row_number > 1;

CREATE UNIQUE INDEX IF NOT EXISTS uq_vehicle_fuel_log_receipt
    ON vehicle_fuel_log(receipt_id)
    WHERE receipt_id IS NOT NULL;

CREATE OR REPLACE FUNCTION sync_fuel_receipt_to_log()
RETURNS trigger AS $$
DECLARE
    v_is_fuel boolean;
    v_vehicle_code text;
    v_odometer integer := 0;
BEGIN
    IF TG_OP = 'DELETE' THEN
        DELETE FROM vehicle_fuel_log WHERE receipt_id = OLD.receipt_id;
        RETURN OLD;
    END IF;

    v_is_fuel :=
        COALESCE(NEW.gl_account_code, '') LIKE '5110%'
        OR LOWER(COALESCE(NEW.category, '')) = 'fuel'
        OR LOWER(COALESCE(NEW.gl_account_name, '')) LIKE '%fuel%';

    IF NOT v_is_fuel THEN
        DELETE FROM vehicle_fuel_log WHERE receipt_id = NEW.receipt_id;
        RETURN NEW;
    END IF;

    IF NEW.vehicle_id IS NOT NULL THEN
        SELECT COALESCE(NULLIF(TRIM(vehicle_number), ''), NEW.vehicle_id::text)
        INTO v_vehicle_code
        FROM vehicles
        WHERE vehicle_id = NEW.vehicle_id;
        v_vehicle_code := COALESCE(v_vehicle_code, NEW.vehicle_id::text);
    ELSE
        v_vehicle_code := 'GENERAL';
    END IF;

    IF NEW.odometer_reading IS NOT NULL THEN
        v_odometer := NEW.odometer_reading;
    ELSIF NEW.charter_id IS NOT NULL THEN
        SELECT COALESCE(odometer_end, odometer_start, 0)::integer
        INTO v_odometer
        FROM charters
        WHERE charter_id = NEW.charter_id;
    END IF;

    INSERT INTO vehicle_fuel_log (
        vehicle_id,
        amount,
        liters,
        charter_id,
        receipt_id,
        recorded_at,
        recorded_by,
        odometer_reading
    )
    VALUES (
        v_vehicle_code,
        COALESCE(NEW.gross_amount, 0),
        COALESCE(NEW.fuel_amount, 0),
        NEW.charter_id,
        NEW.receipt_id,
        NEW.receipt_date::timestamp,
        current_user,
        v_odometer
    )
    ON CONFLICT (receipt_id) WHERE receipt_id IS NOT NULL
    DO UPDATE SET
        vehicle_id = EXCLUDED.vehicle_id,
        amount = EXCLUDED.amount,
        liters = EXCLUDED.liters,
        charter_id = EXCLUDED.charter_id,
        recorded_at = EXCLUDED.recorded_at,
        recorded_by = EXCLUDED.recorded_by,
        odometer_reading = EXCLUDED.odometer_reading;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sync_fuel_to_log ON receipts;
CREATE TRIGGER trg_sync_fuel_to_log
AFTER INSERT OR UPDATE OR DELETE ON receipts
FOR EACH ROW
EXECUTE FUNCTION sync_fuel_receipt_to_log();

INSERT INTO vehicle_fuel_log (
    vehicle_id,
    amount,
    liters,
    charter_id,
    receipt_id,
    recorded_at,
    recorded_by,
    odometer_reading
)
SELECT
    CASE
        WHEN r.vehicle_id IS NULL THEN 'GENERAL'
        ELSE COALESCE(
            NULLIF(TRIM(v.vehicle_number), ''),
            r.vehicle_id::text
        )
    END,
    COALESCE(r.gross_amount, 0),
    COALESCE(r.fuel_amount, 0),
    r.charter_id,
    r.receipt_id,
    r.receipt_date::timestamp,
    'fuel-log-backfill',
    COALESCE(
        r.odometer_reading,
        c.odometer_end::integer,
        c.odometer_start::integer,
        0
    )
FROM receipts r
LEFT JOIN vehicles v ON v.vehicle_id = r.vehicle_id
LEFT JOIN charters c ON c.charter_id = r.charter_id
WHERE COALESCE(r.gl_account_code, '') LIKE '5110%'
   OR LOWER(COALESCE(r.category, '')) = 'fuel'
   OR LOWER(COALESCE(r.gl_account_name, '')) LIKE '%fuel%'
ON CONFLICT (receipt_id) WHERE receipt_id IS NOT NULL
DO UPDATE SET
    vehicle_id = EXCLUDED.vehicle_id,
    amount = EXCLUDED.amount,
    liters = EXCLUDED.liters,
    charter_id = EXCLUDED.charter_id,
    recorded_at = EXCLUDED.recorded_at,
    odometer_reading = EXCLUDED.odometer_reading;
