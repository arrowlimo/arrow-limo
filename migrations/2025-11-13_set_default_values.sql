-- Set safe default values for optional columns used by exporter
-- Date: 2025-11-13

-- 1) vehicle_fuel_log: ensure odometer_reading exists and set defaults
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='vehicle_fuel_log') THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='vehicle_fuel_log' AND column_name='odometer_reading'
        ) THEN
            EXECUTE 'ALTER TABLE vehicle_fuel_log ADD COLUMN odometer_reading INTEGER';
        END IF;
        -- Set defaults for numeric fields used by exporter
        IF EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='vehicle_fuel_log' AND column_name='liters'
        ) THEN
            EXECUTE 'ALTER TABLE vehicle_fuel_log ALTER COLUMN liters SET DEFAULT 0';
            EXECUTE 'UPDATE vehicle_fuel_log SET liters = 0 WHERE liters IS NULL';
        END IF;
        EXECUTE 'ALTER TABLE vehicle_fuel_log ALTER COLUMN odometer_reading SET DEFAULT 0';
        EXECUTE 'UPDATE vehicle_fuel_log SET odometer_reading = 0 WHERE odometer_reading IS NULL';
    END IF;
END $$;

-- 2) charter_charges: set default category and populate missing
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='charter_charges') THEN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='charter_charges' AND column_name='category'
        ) THEN
            EXECUTE 'ALTER TABLE charter_charges ALTER COLUMN category SET DEFAULT ''unspecified''';
            EXECUTE 'UPDATE charter_charges SET category = ''unspecified'' WHERE category IS NULL OR category = ''''';
        END IF;
    END IF;
END $$;

-- 3) clients: prefer empty string defaults for human-facing text fields (non-financial)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='clients') THEN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clients' AND column_name='contact_info'
        ) THEN
            EXECUTE 'ALTER TABLE clients ALTER COLUMN contact_info SET DEFAULT ''''';
            EXECUTE 'UPDATE clients SET contact_info = '''' WHERE contact_info IS NULL';
        END IF;
        IF EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clients' AND column_name='billing_address'
        ) THEN
            EXECUTE 'ALTER TABLE clients ALTER COLUMN billing_address SET DEFAULT ''''';
            EXECUTE 'UPDATE clients SET billing_address = '''' WHERE billing_address IS NULL';
        END IF;
        IF EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clients' AND column_name='notes'
        ) THEN
            EXECUTE 'ALTER TABLE clients ALTER COLUMN notes SET DEFAULT ''''';
            EXECUTE 'UPDATE clients SET notes = '''' WHERE notes IS NULL';
        END IF;
    END IF;
END $$;
