-- Migration: Add direct cash tip and secondary driver fields to charters
-- Safe additive migration; no destructive changes.
ALTER TABLE charters
    ADD COLUMN IF NOT EXISTS cash_tip_amount DECIMAL(10,2) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS secondary_driver_id INTEGER REFERENCES employees(employee_id),
    ADD COLUMN IF NOT EXISTS secondary_driver_name VARCHAR(200);

-- Optional index to speed up queries involving cash tips
CREATE INDEX IF NOT EXISTS idx_charters_cash_tip_amount ON charters(cash_tip_amount);
CREATE INDEX IF NOT EXISTS idx_charters_secondary_driver_id ON charters(secondary_driver_id);
