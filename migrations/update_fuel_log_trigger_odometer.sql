-- Migration: Update fuel log trigger to use receipt odometer
-- Date: 2026-02-15
-- Purpose: Prioritize odometer reading from receipt over charter

-- Updated function to sync fuel receipts to vehicle_fuel_log
CREATE OR REPLACE FUNCTION sync_fuel_receipt_to_log()
RETURNS TRIGGER AS $$
DECLARE
    v_odometer INTEGER := 0;
BEGIN
    -- Only process if this is a fuel receipt with a vehicle
    IF NEW.category = 'fuel' AND NEW.vehicle_id IS NOT NULL THEN
        
        -- PRIORITY 1: Use odometer from receipt if directly entered
        IF NEW.odometer_reading IS NOT NULL THEN
            v_odometer := NEW.odometer_reading;
        -- PRIORITY 2: Try to get odometer reading from linked charter
        ELSIF NEW.charter_id IS NOT NULL THEN
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
                v_odometer
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
                    v_odometer
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

-- Trigger already exists from migration 003, just recreate to be safe
DROP TRIGGER IF EXISTS trg_sync_fuel_to_log ON receipts;
CREATE TRIGGER trg_sync_fuel_to_log
AFTER INSERT OR UPDATE ON receipts
FOR EACH ROW
EXECUTE FUNCTION sync_fuel_receipt_to_log();

-- Verify trigger exists
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_trigger 
        WHERE tgname = 'trg_sync_fuel_to_log'
    ) THEN
        RAISE NOTICE 'Trigger trg_sync_fuel_to_log successfully updated';
    ELSE
        RAISE EXCEPTION 'Failed to create trigger';
    END IF;
END $$;
