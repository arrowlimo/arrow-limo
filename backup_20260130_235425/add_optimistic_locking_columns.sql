-- Optimistic Locking: Add version and updated_at columns
-- Run this against both local and Neon databases

-- Add columns to charters
ALTER TABLE charters 
ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

-- Add columns to payments
ALTER TABLE payments 
ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

-- Add columns to receipts
ALTER TABLE receipts 
ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

-- Add columns to employees
ALTER TABLE employees 
ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

-- Add columns to vehicles
ALTER TABLE vehicles 
ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

-- Create trigger function to auto-update updated_at on changes
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers to auto-update timestamp
DROP TRIGGER IF EXISTS update_charters_updated_at ON charters;
CREATE TRIGGER update_charters_updated_at
    BEFORE UPDATE ON charters
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_payments_updated_at ON payments;
CREATE TRIGGER update_payments_updated_at
    BEFORE UPDATE ON payments
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_receipts_updated_at ON receipts;
CREATE TRIGGER update_receipts_updated_at
    BEFORE UPDATE ON receipts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_employees_updated_at ON employees;
CREATE TRIGGER update_employees_updated_at
    BEFORE UPDATE ON employees
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_vehicles_updated_at ON vehicles;
CREATE TRIGGER update_vehicles_updated_at
    BEFORE UPDATE ON vehicles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_charters_updated_at ON charters(updated_at);
CREATE INDEX IF NOT EXISTS idx_payments_updated_at ON payments(updated_at);
CREATE INDEX IF NOT EXISTS idx_receipts_updated_at ON receipts(updated_at);

COMMIT;

-- Verification queries
SELECT 'charters' AS table_name, 
       COUNT(*) AS total_rows,
       COUNT(version) AS has_version,
       COUNT(updated_at) AS has_updated_at
FROM charters
UNION ALL
SELECT 'payments', COUNT(*), COUNT(version), COUNT(updated_at) FROM payments
UNION ALL
SELECT 'receipts', COUNT(*), COUNT(version), COUNT(updated_at) FROM receipts
UNION ALL
SELECT 'employees', COUNT(*), COUNT(version), COUNT(updated_at) FROM employees
UNION ALL
SELECT 'vehicles', COUNT(*), COUNT(version), COUNT(updated_at) FROM vehicles;
