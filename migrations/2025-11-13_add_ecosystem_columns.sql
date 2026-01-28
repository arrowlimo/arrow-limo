-- Add columns required by exporter ecosystems
-- Date: 2025-11-13

-- 1) charter_charges: add category if missing
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='charter_charges') THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='charter_charges' AND column_name='category'
        ) THEN
            EXECUTE 'ALTER TABLE charter_charges ADD COLUMN category VARCHAR(100)';
        END IF;
    END IF;
END $$;

-- 2) vehicle_fuel_log: add liters if missing
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='vehicle_fuel_log') THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='vehicle_fuel_log' AND column_name='liters'
        ) THEN
            EXECUTE 'ALTER TABLE vehicle_fuel_log ADD COLUMN liters DECIMAL(8,2)';
        END IF;
    END IF;
END $$;
