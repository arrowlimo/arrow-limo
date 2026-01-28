-- Add payroll and HOS fields to charters and run_charters (idempotent)
ALTER TABLE IF EXISTS charters
  ADD COLUMN IF NOT EXISTS employee_id INTEGER,
  ADD COLUMN IF NOT EXISTS approved_hours NUMERIC(10,2) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS gratuity_amount NUMERIC(12,2) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS tip_splits JSONB,
  ADD COLUMN IF NOT EXISTS advances NUMERIC(12,2) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS floats NUMERIC(12,2) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS reimbursed_receipts NUMERIC(12,2) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS on_duty_driving NUMERIC(10,2) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS on_duty_not_driving NUMERIC(10,2) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS off_duty_break NUMERIC(10,2) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS off_duty NUMERIC(10,2) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS duty_log JSONB,
  ADD COLUMN IF NOT EXISTS beverage_invoice_separately BOOLEAN DEFAULT FALSE;

ALTER TABLE IF EXISTS run_charters
  ADD COLUMN IF NOT EXISTS approved_hours NUMERIC(10,2) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS hours_locked BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS itemized_liquor_orders JSONB;

-- Optional index for employee-period queries
CREATE INDEX IF NOT EXISTS idx_charters_employee_date ON charters (employee_id, charter_date);