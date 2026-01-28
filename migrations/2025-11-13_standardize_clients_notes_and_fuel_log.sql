-- Standardize clients.notes and vehicle_fuel_log schema
-- Date: 2025-11-13

-- 1) Ensure clients.notes exists and backfill from collection_notes if present
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='clients') THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clients' AND column_name='notes'
        ) THEN
            EXECUTE 'ALTER TABLE clients ADD COLUMN notes TEXT';
        END IF;
        IF EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clients' AND column_name='collection_notes'
        ) THEN
            EXECUTE 'UPDATE clients SET notes = COALESCE(notes, collection_notes) WHERE notes IS NULL AND collection_notes IS NOT NULL';
        END IF;
    END IF;
END $$;

-- 2) Ensure vehicle_fuel_log has expected columns and primary key
DO $$
DECLARE
    has_log_id BOOLEAN;
    has_vehicle_id BOOLEAN;
    has_receipt_id BOOLEAN;
    has_pk BOOLEAN;
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='vehicle_fuel_log') THEN
        SELECT EXISTS(
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='vehicle_fuel_log' AND column_name='log_id'
        ) INTO has_log_id;
        SELECT EXISTS(
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='vehicle_fuel_log' AND column_name='vehicle_id'
        ) INTO has_vehicle_id;
        SELECT EXISTS(
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='vehicle_fuel_log' AND column_name='receipt_id'
        ) INTO has_receipt_id;

        -- Add columns if missing
        IF NOT has_log_id THEN
            EXECUTE 'ALTER TABLE vehicle_fuel_log ADD COLUMN log_id SERIAL';
        END IF;
        IF NOT has_vehicle_id THEN
            EXECUTE 'ALTER TABLE vehicle_fuel_log ADD COLUMN vehicle_id VARCHAR(50)';
        END IF;
        IF NOT has_receipt_id THEN
            EXECUTE 'ALTER TABLE vehicle_fuel_log ADD COLUMN receipt_id INTEGER';
        END IF;

        -- Add PK on log_id if table has no primary key
        SELECT EXISTS (
            SELECT 1
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE c.contype = 'p' AND n.nspname = 'public' AND t.relname = 'vehicle_fuel_log'
        ) INTO has_pk;

        IF NOT has_pk THEN
            -- Try to set log_id as primary key if not already
            -- Add a unique index first to avoid issues with existing duplicates
            EXECUTE 'CREATE UNIQUE INDEX IF NOT EXISTS vehicle_fuel_log_log_id_uidx ON vehicle_fuel_log (log_id)';
            BEGIN
                EXECUTE 'ALTER TABLE vehicle_fuel_log ADD CONSTRAINT vehicle_fuel_log_pkey PRIMARY KEY (log_id)';
            EXCEPTION WHEN duplicate_object THEN
                -- Ignore if PK created elsewhere
                NULL;
            END;
        END IF;
    END IF;
END $$;
