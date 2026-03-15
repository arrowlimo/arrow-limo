-- Migration: Auto-populate vehicle_fuel_log from fuel receipts
-- Date: 2026-02-07
-- Purpose: Ensure fuel purchases automatically create vehicle_fuel_log entries
--          for tracking consumption, odometer readings, and costs per vehicle

-- First, update the vehicle_fuel_log liters column to match receipts precision
ALTER TABLE vehicle_fuel_log 
ALTER COLUMN liters TYPE numeric(12,3);

-- Function to sync fuel receipts to vehicle_fuel_log
CREATE OR REPLACE FUNCTION sync_fuel_receipt_to_log()
RETURNS TRIGGER AS $$
DECLARE
    v_odometer INTEGER := 0;
BEGIN
    -- Only process if this is a fuel receipt with a vehicle
    IF NEW.category = 'fuel' AND NEW.vehicle_id IS NOT NULL THEN
        
        -- Try to get odometer reading from linked charter
        IF NEW.charter_id IS NOT NULL THEN
            SELECT COALESCE(odometer_end, odometer_start, 0)
            INTO v_odometer
            FROM charters
            WHERE charter_id = NEW.charter_id;
        END IF;
        
        -- Check if log entry already exists for this receipt
        IF TG_OP = 'INSERT' THEN
            INSERT INTO vehicle_fuel_log (
                vehicle_id,
                amount,
                liters,
                charter_id,
                receipt_id,
                recorded_at,
                recorded_by,
                odometer_reading
            ) VALUES (
                NEW.vehicle_id,
                NEW.gross_amount,
                COALESCE(NEW.fuel_amount, 0),
                NEW.charter_id,
                NEW.receipt_id,
                NEW.receipt_date,
                current_user,
                v_odometer  -- Pulled from charter if available
            );
            
        ELSIF TG_OP = 'UPDATE' THEN
            -- Update existing log entry if receipt_id matches
            UPDATE vehicle_fuel_log SET
                vehicle_id = NEW.vehicle_id,
                amount = NEW.gross_amount,
                liters = COALESCE(NEW.fuel_amount, 0),
                charter_id = NEW.charter_id,
                recorded_at = NEW.receipt_date,
                odometer_reading = v_odometer
            WHERE receipt_id = NEW.receipt_id;
            
            -- If no entry exists (was not fuel before), create one
            IF NOT FOUND THEN
                INSERT INTO vehicle_fuel_log (
                    vehicle_id,
                    amount,
                    liters,
                    charter_id,
                    receipt_id,
                    recorded_at,
                    recorded_by,
                    odometer_reading
                ) VALUES (
                    NEW.vehicle_id,
                    NEW.gross_amount,
                    COALESCE(NEW.fuel_amount, 0),
                    NEW.charter_id,
                    NEW.receipt_id,
                    NEW.receipt_date,
                    current_user,
                    0
                );
            END IF;
        END IF;
        
    ELSIF TG_OP = 'UPDATE' AND (OLD.category = 'fuel' AND NEW.category != 'fuel') THEN
        -- Receipt category changed FROM fuel - remove from log
        DELETE FROM vehicle_fuel_log WHERE receipt_id = NEW.receipt_id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger on receipts table
DROP TRIGGER IF EXISTS trg_sync_fuel_to_log ON receipts;
CREATE TRIGGER trg_sync_fuel_to_log
    AFTER INSERT OR UPDATE ON receipts
    FOR EACH ROW
    EXECUTE FUNCTION sync_fuel_receipt_to_log();

-- Backfill existing fuel receipts into vehicle_fuel_log
-- (only if they don't already have an entry)
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
    r.vehicle_id,
    r.gross_amount,
    COALESCE(r.fuel_amount, 0),
    r.charter_id,
    r.receipt_id,
    r.receipt_date,
    'migration',
    0
FROM receipts r
WHERE r.category = 'fuel' 
    AND r.vehicle_id IS NOT NULL
    AND NOT EXISTS (
        SELECT 1 FROM vehicle_fuel_log vfl 
        WHERE vfl.receipt_id = r.receipt_id
    );

-- Create index for better performance
CREATE INDEX IF NOT EXISTS idx_vehicle_fuel_log_vehicle_date 
    ON vehicle_fuel_log(vehicle_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_vehicle_fuel_log_receipt 
    ON vehicle_fuel_log(receipt_id);

-- Verify sync is working
SELECT 
    COUNT(*) as fuel_receipts,
    COUNT(DISTINCT vehicle_id) as vehicles_with_fuel,
    SUM(fuel_amount) as total_liters,
    SUM(gross_amount) as total_cost
FROM receipts 
WHERE category = 'fuel' AND vehicle_id IS NOT NULL;

SELECT 
    COUNT(*) as fuel_log_entries,
    COUNT(DISTINCT vehicle_id) as vehicles_in_log,
    SUM(liters) as total_liters_logged,
    SUM(amount) as total_cost_logged
FROM vehicle_fuel_log;
-- Create view for fuel consumption analysis (odometer calculations done at report time)
CREATE OR REPLACE VIEW vw_vehicle_fuel_consumption AS
SELECT 
    vfl.vehicle_id,
    v.vehicle_number,
    v.make,
    v.model,
    v.year,
    vfl.recorded_at AS fuel_date,
    vfl.liters,
    vfl.amount AS fuel_cost,
    vfl.odometer_reading,
    vfl.charter_id,
    vfl.receipt_id,
    c.reserve_number,
    -- Calculate odometer difference from previous fill
    vfl.odometer_reading - LAG(vfl.odometer_reading) OVER (
        PARTITION BY vfl.vehicle_id 
        ORDER BY vfl.recorded_at
    ) AS odometer_diff,
    -- Calculate L/100km when we have odometer readings
    CASE 
        WHEN vfl.odometer_reading > 0 
            AND LAG(vfl.odometer_reading) OVER (PARTITION BY vfl.vehicle_id ORDER BY vfl.recorded_at) > 0
            AND vfl.odometer_reading - LAG(vfl.odometer_reading) OVER (PARTITION BY vfl.vehicle_id ORDER BY vfl.recorded_at) > 0
        THEN ROUND(
            (vfl.liters * 100.0) / 
            NULLIF(vfl.odometer_reading - LAG(vfl.odometer_reading) OVER (PARTITION BY vfl.vehicle_id ORDER BY vfl.recorded_at), 0),
            2
        )
        ELSE NULL
    END AS liters_per_100km,
    -- Cost per liter
    CASE WHEN vfl.liters > 0 
        THEN ROUND(vfl.amount / vfl.liters, 3)
        ELSE NULL
    END AS cost_per_liter,
    -- Days since last fill
    vfl.recorded_at::date - LAG(vfl.recorded_at::date) OVER (
        PARTITION BY vfl.vehicle_id 
        ORDER BY vfl.recorded_at
    ) AS days_since_last_fill
FROM vehicle_fuel_log vfl
LEFT JOIN vehicles v ON v.vehicle_id = vfl.vehicle_id
LEFT JOIN charters c ON c.charter_id = vfl.charter_id
ORDER BY vfl.vehicle_id, vfl.recorded_at DESC;

-- Create materialized view for faster fuel cost summary reports
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_vehicle_fuel_summary AS
SELECT 
    v.vehicle_id,
    v.vehicle_number,
    v.make,
    v.model,
    v.year,
    COUNT(vfl.id) AS total_fills,
    SUM(vfl.liters) AS total_liters,
    SUM(vfl.amount) AS total_cost,
    ROUND(AVG(vfl.amount / NULLIF(vfl.liters, 0)), 3) AS avg_cost_per_liter,
    MAX(vfl.recorded_at) AS last_fuel_date,
    MIN(vfl.recorded_at) AS first_fuel_date,
    -- Calculate avg consumption for entries with valid odometer data
    ROUND(AVG(
        CASE 
            WHEN vfl.odometer_reading > 0 
                AND LAG(vfl.odometer_reading) OVER (PARTITION BY vfl.vehicle_id ORDER BY vfl.recorded_at) > 0
                AND vfl.odometer_reading - LAG(vfl.odometer_reading) OVER (PARTITION BY vfl.vehicle_id ORDER BY vfl.recorded_at) > 0
            THEN (vfl.liters * 100.0) / 
                NULLIF(vfl.odometer_reading - LAG(vfl.odometer_reading) OVER (PARTITION BY vfl.vehicle_id ORDER BY vfl.recorded_at), 0)
            ELSE NULL
        END
    ), 2) AS avg_liters_per_100km
FROM vehicles v
LEFT JOIN vehicle_fuel_log vfl ON v.vehicle_id = vfl.vehicle_id
GROUP BY v.vehicle_id, v.vehicle_number, v.make, v.model, v.year
HAVING COUNT(vfl.id) > 0;

-- Create index for materialized view refresh
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_vehicle_fuel_summary_vehicle 
    ON mv_vehicle_fuel_summary(vehicle_id);

COMMENT ON TABLE vehicle_fuel_log IS 'Vehicle fuel consumption tracking - auto-synced from receipts with category=fuel';
COMMENT ON COLUMN vehicle_fuel_log.receipt_id IS 'Links to receipts table - auto-populated by trigger';
COMMENT ON COLUMN vehicle_fuel_log.liters IS 'Fuel amount in liters (3 decimal precision for exact measurements)';
COMMENT ON COLUMN vehicle_fuel_log.odometer_reading IS 'Odometer reading at time of fueling - pulled from charter if available, calculated for reports';
COMMENT ON VIEW vw_vehicle_fuel_consumption IS 'Real-time fuel consumption analysis with L/100km calculations done at query time';
COMMENT ON MATERIALIZED VIEW mv_vehicle_fuel_summary IS 'Cached vehicle fuel cost summary - refresh periodically for report
COMMENT ON COLUMN vehicle_fuel_log.odometer_reading IS 'Odometer reading at time of fueling - used for consumption calculations';
