-- Migration 0061: Tenant pilot scaffold (additive, non-disruptive)
-- Purpose:
--   1) Add tenant_id to pilot tables (if table exists)
--   2) Add tenant_id indexes to support backfill and future distribution
-- Notes:
--   - This migration does NOT perform table distribution.
--   - Backfill/validation must complete before any NOT NULL or distribution actions.

ALTER TABLE IF EXISTS charters ADD COLUMN IF NOT EXISTS tenant_id TEXT;
CREATE INDEX IF NOT EXISTS idx_charters_tenant_id ON charters (tenant_id);

ALTER TABLE IF EXISTS charter_charges ADD COLUMN IF NOT EXISTS tenant_id TEXT;
CREATE INDEX IF NOT EXISTS idx_charter_charges_tenant_id ON charter_charges (tenant_id);

ALTER TABLE IF EXISTS receipts ADD COLUMN IF NOT EXISTS tenant_id TEXT;
CREATE INDEX IF NOT EXISTS idx_receipts_tenant_id ON receipts (tenant_id);

ALTER TABLE IF EXISTS payments ADD COLUMN IF NOT EXISTS tenant_id TEXT;
CREATE INDEX IF NOT EXISTS idx_payments_tenant_id ON payments (tenant_id);

ALTER TABLE IF EXISTS invoices ADD COLUMN IF NOT EXISTS tenant_id TEXT;
CREATE INDEX IF NOT EXISTS idx_invoices_tenant_id ON invoices (tenant_id);

ALTER TABLE IF EXISTS clients ADD COLUMN IF NOT EXISTS tenant_id TEXT;
CREATE INDEX IF NOT EXISTS idx_clients_tenant_id ON clients (tenant_id);

ALTER TABLE IF EXISTS banking_transactions ADD COLUMN IF NOT EXISTS tenant_id TEXT;
CREATE INDEX IF NOT EXISTS idx_banking_transactions_tenant_id ON banking_transactions (tenant_id);

ALTER TABLE IF EXISTS payroll_entries ADD COLUMN IF NOT EXISTS tenant_id TEXT;
CREATE INDEX IF NOT EXISTS idx_payroll_entries_tenant_id ON payroll_entries (tenant_id);

ALTER TABLE IF EXISTS employees ADD COLUMN IF NOT EXISTS tenant_id TEXT;
CREATE INDEX IF NOT EXISTS idx_employees_tenant_id ON employees (tenant_id);

ALTER TABLE IF EXISTS vehicles ADD COLUMN IF NOT EXISTS tenant_id TEXT;
CREATE INDEX IF NOT EXISTS idx_vehicles_tenant_id ON vehicles (tenant_id);
