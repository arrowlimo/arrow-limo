-- Actual schema renames to standardize column/table names
-- Date: 2025-11-13

-- 1) Rename misnamed staging table
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'staging_driver_pay'
    ) THEN
        EXECUTE 'ALTER TABLE staging_driver_pay RENAME TO staging_qb_accounts';
    END IF;
END $$;

-- 2) Clients table: address -> billing_address, phone_number -> contact_info, add square_customer_id, warning_flag
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='clients') THEN
        -- address -> billing_address
        IF EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clients' AND column_name='address'
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clients' AND column_name='billing_address'
        ) THEN
            EXECUTE 'ALTER TABLE clients RENAME COLUMN address TO billing_address';
        END IF;
        -- phone_number -> contact_info
        IF EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clients' AND column_name='phone_number'
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clients' AND column_name='contact_info'
        ) THEN
            EXECUTE 'ALTER TABLE clients RENAME COLUMN phone_number TO contact_info';
        END IF;
        -- add square_customer_id if missing
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clients' AND column_name='square_customer_id'
        ) THEN
            EXECUTE 'ALTER TABLE clients ADD COLUMN square_customer_id VARCHAR(100)';
        END IF;
        -- add warning_flag if missing
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clients' AND column_name='warning_flag'
        ) THEN
            EXECUTE 'ALTER TABLE clients ADD COLUMN warning_flag BOOLEAN DEFAULT FALSE';
        END IF;
    END IF;
END $$;

-- 3) Vehicles table: vehicle_code -> vehicle_type, unit -> unit_number, mileage -> current_mileage, vehicle_status -> status
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='vehicles') THEN
        -- vehicle_code -> vehicle_type
        IF EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='vehicles' AND column_name='vehicle_code'
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='vehicles' AND column_name='vehicle_type'
        ) THEN
            EXECUTE 'ALTER TABLE vehicles RENAME COLUMN vehicle_code TO vehicle_type';
        END IF;
        -- unit -> unit_number
        IF EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='vehicles' AND column_name='unit'
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='vehicles' AND column_name='unit_number'
        ) THEN
            EXECUTE 'ALTER TABLE vehicles RENAME COLUMN unit TO unit_number';
        END IF;
        -- mileage -> current_mileage
        IF EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='vehicles' AND column_name='mileage'
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='vehicles' AND column_name='current_mileage'
        ) THEN
            EXECUTE 'ALTER TABLE vehicles RENAME COLUMN mileage TO current_mileage';
        END IF;
        -- vehicle_status -> status
        IF EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='vehicles' AND column_name='vehicle_status'
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='vehicles' AND column_name='status'
        ) THEN
            EXECUTE 'ALTER TABLE vehicles RENAME COLUMN vehicle_status TO status';
        END IF;
        -- add missing columns if none of the above exist
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='vehicles' AND column_name='unit_number'
        ) THEN
            EXECUTE 'ALTER TABLE vehicles ADD COLUMN unit_number VARCHAR(50)';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='vehicles' AND column_name='current_mileage'
        ) THEN
            EXECUTE 'ALTER TABLE vehicles ADD COLUMN current_mileage INTEGER';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='vehicles' AND column_name='status'
        ) THEN
            EXECUTE 'ALTER TABLE vehicles ADD COLUMN status VARCHAR(50)';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='vehicles' AND column_name='vehicle_type'
        ) THEN
            EXECUTE 'ALTER TABLE vehicles ADD COLUMN vehicle_type VARCHAR(100)';
        END IF;
    END IF;
END $$;

-- 4) Receipts table: id -> receipt_id
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='receipts') THEN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='receipts' AND column_name='id'
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='receipts' AND column_name='receipt_id'
        ) THEN
            EXECUTE 'ALTER TABLE receipts RENAME COLUMN id TO receipt_id';
        END IF;
    END IF;
END $$;

-- 5) Banking transactions: linked_receipt_id -> receipt_id
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='banking_transactions') THEN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='banking_transactions' AND column_name='linked_receipt_id'
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='banking_transactions' AND column_name='receipt_id'
        ) THEN
            EXECUTE 'ALTER TABLE banking_transactions RENAME COLUMN linked_receipt_id TO receipt_id';
        END IF;
        -- Add receipt_id if absent entirely
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='banking_transactions' AND column_name='receipt_id'
        ) THEN
            EXECUTE 'ALTER TABLE banking_transactions ADD COLUMN receipt_id INTEGER';
        END IF;
    END IF;
END $$;

-- 6) Employees: add termination_date if missing
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='employees') THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='employees' AND column_name='termination_date'
        ) THEN
            EXECUTE 'ALTER TABLE employees ADD COLUMN termination_date DATE';
        END IF;
    END IF;
END $$;
