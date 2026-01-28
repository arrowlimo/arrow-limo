-- Unify problematic naming and provide stable views across schema variations
-- Date: 2025-11-13

-- Safely rename misnamed staging table if present
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'staging_driver_pay'
    ) THEN
        EXECUTE 'ALTER TABLE staging_driver_pay RENAME TO staging_qb_accounts';
    END IF;
END $$;

-- Create unified clients view with defensive columns
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='clients'
    ) THEN
        PERFORM 1;
        EXECUTE (
            'CREATE OR REPLACE VIEW clients_unified AS \n'
            || 'SELECT \n'
            || '  client_id, \n'
            || '  client_name, \n'
            || '  email, \n'
            || '  ' || (CASE WHEN EXISTS (
                    SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clients' AND column_name='billing_address'
                ) THEN 'billing_address' ELSE 'NULL::text AS billing_address' END) || ',\n'
            || '  ' || (CASE WHEN EXISTS (
                    SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clients' AND column_name='contact_info'
                ) THEN 'contact_info' ELSE (CASE WHEN EXISTS (
                    SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clients' AND column_name='phone_number'
                ) THEN 'phone_number' ELSE 'NULL::text AS contact_info' END) END) || ',\n'
            || '  ' || (CASE WHEN EXISTS (
                    SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clients' AND column_name='warning_flag'
                ) THEN 'warning_flag' ELSE 'NULL::boolean AS warning_flag' END) || ',\n'
            || '  ' || (CASE WHEN EXISTS (
                    SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clients' AND column_name='square_customer_id'
                ) THEN 'square_customer_id' ELSE 'NULL::text AS square_customer_id' END) || ',\n'
            || '  notes, \n'
            || '  created_at \n'
            || 'FROM clients'
        );
    END IF;
END $$;

-- Create unified vehicles view handling vehicle_type/code and optional status/mileage
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='vehicles'
    ) THEN
        EXECUTE (
            'CREATE OR REPLACE VIEW vehicles_unified AS \n'
            || 'SELECT \n'
            || '  vehicle_id, \n'
            || '  ' || (CASE WHEN EXISTS (
                    SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='vehicles' AND column_name='unit_number'
                ) THEN 'unit_number' ELSE 'NULL::text AS unit_number' END) || ',\n'
            || '  ' || (CASE WHEN EXISTS (
                    SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='vehicles' AND column_name='vehicle_type'
                ) THEN 'vehicle_type' ELSE (CASE WHEN EXISTS (
                    SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='vehicles' AND column_name='vehicle_code'
                ) THEN 'vehicle_code AS vehicle_type' ELSE 'NULL::text AS vehicle_type' END) END) || ',\n'
            || '  make, model, year, vin_number, license_plate, passenger_capacity, \n'
            || '  ' || (CASE WHEN EXISTS (
                    SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='vehicles' AND column_name='status'
                ) THEN 'status' ELSE 'NULL::text AS status' END) || ',\n'
            || '  ' || (CASE WHEN EXISTS (
                    SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='vehicles' AND column_name='current_mileage'
                ) THEN 'current_mileage' ELSE 'NULL::integer AS current_mileage' END) || '\n'
            || 'FROM vehicles'
        );
    END IF;
END $$;

-- Create unified receipts view exposing a stable primary key name
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='receipts'
    ) THEN
        EXECUTE (
            'CREATE OR REPLACE VIEW receipts_unified AS \n'
            || 'SELECT \n'
            || '  ' || (CASE WHEN EXISTS (
                    SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='receipts' AND column_name='receipt_id'
                ) THEN 'receipt_id' ELSE (CASE WHEN EXISTS (
                    SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='receipts' AND column_name='id'
                ) THEN 'id AS receipt_id' ELSE 'NULL::integer AS receipt_id' END) END) || ',\n'
            || '  vendor_name, gross_amount, gst_amount, net_amount, receipt_date, category, \n'
            || '  ' || (CASE WHEN EXISTS (
                    SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='receipts' AND column_name='employee_id'
                ) THEN 'employee_id' ELSE 'NULL::integer AS employee_id' END) || ',\n'
            || '  ' || (CASE WHEN EXISTS (
                    SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='receipts' AND column_name='vehicle_id'
                ) THEN 'vehicle_id' ELSE 'NULL::integer AS vehicle_id' END) || '\n'
            || 'FROM receipts'
        );
    END IF;
END $$;

-- Create unified banking transactions view with optional columns
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='banking_transactions'
    ) THEN
        EXECUTE (
            'CREATE OR REPLACE VIEW banking_transactions_unified AS \n'
            || 'SELECT \n'
            || '  transaction_id, account_number, transaction_date, description, debit_amount, credit_amount, balance, \n'
            || '  ' || (CASE WHEN EXISTS (
                    SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='banking_transactions' AND column_name='vendor_extracted'
                ) THEN 'vendor_extracted' ELSE 'NULL::text AS vendor_extracted' END) || ',\n'
            || '  ' || (CASE WHEN EXISTS (
                    SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='banking_transactions' AND column_name='category'
                ) THEN 'category' ELSE 'NULL::text AS category' END) || ',\n'
            || '  ' || (CASE WHEN EXISTS (
                    SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='banking_transactions' AND column_name='receipt_id'
                ) THEN 'receipt_id' ELSE 'NULL::integer AS receipt_id' END) || ',\n'
            || '  ' || (CASE WHEN EXISTS (
                    SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='banking_transactions' AND column_name='created_at'
                ) THEN 'created_at' ELSE 'NULL::timestamp AS created_at' END) || '\n'
            || 'FROM banking_transactions'
        );
    END IF;
END $$;

-- Create unified employees view exposing termination_date if present
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='employees'
    ) THEN
        EXECUTE (
            'CREATE OR REPLACE VIEW employees_unified AS \n'
            || 'SELECT \n'
            || '  employee_id, employee_number, full_name, first_name, last_name, position, hire_date, \n'
            || '  ' || (CASE WHEN EXISTS (
                    SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='employees' AND column_name='termination_date'
                ) THEN 'termination_date' ELSE 'NULL::date AS termination_date' END) || ',\n'
            || '  status, hourly_rate, is_chauffeur \n'
            || 'FROM employees'
        );
    END IF;
END $$;
