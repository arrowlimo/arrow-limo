-- Create payroll_remittances Table
-- CRA Compliance: Track monthly remittance payments and reconciliation
-- Run Date: February 16, 2026
--
-- Purpose: Links monthly PD7A calculations to actual CRA payments
-- Enables: Audit trail, late payment detection, variance analysis

BEGIN;

CREATE TABLE IF NOT EXISTS payroll_remittances (
    remittance_id SERIAL PRIMARY KEY,
    fiscal_year INTEGER NOT NULL,
    remittance_month INTEGER NOT NULL CHECK (remittance_month BETWEEN 1 AND 12),
    
    -- Calculated amounts (from employee_pay_master aggregation)
    calculated_gross DECIMAL(10,2) DEFAULT 0.00,
    calculated_cpp_employee DECIMAL(10,2) DEFAULT 0.00,
    calculated_cpp_employer DECIMAL(10,2) DEFAULT 0.00,
    calculated_ei_employee DECIMAL(10,2) DEFAULT 0.00,
    calculated_ei_employer DECIMAL(10,2) DEFAULT 0.00,
    calculated_federal_tax DECIMAL(10,2) DEFAULT 0.00,
    calculated_provincial_tax DECIMAL(10,2) DEFAULT 0.00,
    calculated_total_remittance DECIMAL(10,2) DEFAULT 0.00,
    
    -- Payment information
    due_date DATE,                                      -- CRA deadline (15th of following month)
    payment_date DATE,                                  -- When actually paid
    payment_amount DECIMAL(10,2),                       -- Actual amount paid
    payment_method TEXT,                                -- Cheque, wire transfer, online banking
    payment_reference TEXT,                             -- Cheque #, confirmation #, etc.
    receipt_id INTEGER,                                 -- Link to receipts table (if tracked)
    
    -- PD7A reconciliation
    pd7a_statement_amount DECIMAL(10,2),               -- From official CRA PD7A statement
    pd7a_filed_date DATE,                              -- When PD7A was filed
    variance DECIMAL(10,2),                            -- calculated_total - pd7a_statement_amount
    reconciled BOOLEAN DEFAULT FALSE,
    
    -- Status tracking
    status TEXT DEFAULT 'pending',                     -- pending, paid, late, reconciled
    is_late BOOLEAN DEFAULT FALSE,                     -- payment_date > due_date
    
    -- Notes
    notes TEXT,
    
    -- Audit trail
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by TEXT,
    
    -- Unique constraint: one record per year/month
    UNIQUE (fiscal_year, remittance_month)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_payroll_remittances_year_month 
    ON payroll_remittances(fiscal_year, remittance_month);

CREATE INDEX IF NOT EXISTS idx_payroll_remittances_status 
    ON payroll_remittances(status);

CREATE INDEX IF NOT EXISTS idx_payroll_remittances_reconciled 
    ON payroll_remittances(reconciled);

-- Create update trigger for updated_at
CREATE OR REPLACE FUNCTION update_payroll_remittances_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_payroll_remittances_updated_at 
    ON payroll_remittances;

CREATE TRIGGER trigger_update_payroll_remittances_updated_at
BEFORE UPDATE ON payroll_remittances
FOR EACH ROW
EXECUTE FUNCTION update_payroll_remittances_updated_at();

COMMIT;

-- Verify table created
SELECT 
    table_name, 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns
WHERE table_name = 'payroll_remittances'
ORDER BY ordinal_position;
