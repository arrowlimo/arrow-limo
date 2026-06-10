-- Migration 0062: Tenant pilot NOT NULL enforcement
-- Purpose:
--   Enforce tenant_id as NOT NULL on pilot tables after successful backfill.
-- Notes:
--   - Assumes 0061 scaffold + backfill validation already completed.
--   - Uses guarded DO blocks so missing tables/columns are skipped safely.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'charters' AND column_name = 'tenant_id'
    ) THEN
        EXECUTE 'ALTER TABLE charters ALTER COLUMN tenant_id SET NOT NULL';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'charter_charges' AND column_name = 'tenant_id'
    ) THEN
        EXECUTE 'ALTER TABLE charter_charges ALTER COLUMN tenant_id SET NOT NULL';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'receipts' AND column_name = 'tenant_id'
    ) THEN
        EXECUTE 'ALTER TABLE receipts ALTER COLUMN tenant_id SET NOT NULL';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'payments' AND column_name = 'tenant_id'
    ) THEN
        EXECUTE 'ALTER TABLE payments ALTER COLUMN tenant_id SET NOT NULL';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'invoices' AND column_name = 'tenant_id'
    ) THEN
        EXECUTE 'ALTER TABLE invoices ALTER COLUMN tenant_id SET NOT NULL';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'clients' AND column_name = 'tenant_id'
    ) THEN
        EXECUTE 'ALTER TABLE clients ALTER COLUMN tenant_id SET NOT NULL';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'banking_transactions' AND column_name = 'tenant_id'
    ) THEN
        EXECUTE 'ALTER TABLE banking_transactions ALTER COLUMN tenant_id SET NOT NULL';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'payroll_entries' AND column_name = 'tenant_id'
    ) THEN
        EXECUTE 'ALTER TABLE payroll_entries ALTER COLUMN tenant_id SET NOT NULL';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'employees' AND column_name = 'tenant_id'
    ) THEN
        EXECUTE 'ALTER TABLE employees ALTER COLUMN tenant_id SET NOT NULL';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'vehicles' AND column_name = 'tenant_id'
    ) THEN
        EXECUTE 'ALTER TABLE vehicles ALTER COLUMN tenant_id SET NOT NULL';
    END IF;
END $$;
