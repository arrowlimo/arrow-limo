-- Migration: Create payroll_adjustments table for segregating adjustment entries
-- Date: 2025-11-07
-- Purpose: Separate reconciliation adjustments from driver wage records

CREATE TABLE IF NOT EXISTS payroll_adjustments (
    adjustment_id SERIAL PRIMARY KEY,
    driver_payroll_id INTEGER NOT NULL REFERENCES driver_payroll(id) ON DELETE RESTRICT,
    adjustment_type VARCHAR(50) NOT NULL, 
    -- e.g., PDF_DB_RECONCILIATION, LEGACY_CORRECTION, BULK_IMPORT, REVERSAL
    
    gross_amount NUMERIC(12,2) NOT NULL,
    net_amount NUMERIC(12,2),
    
    -- Audit fields
    rationale TEXT, -- descriptive explanation
    source_reference TEXT, -- original source / batch id
    original_pay_date DATE,
    year INTEGER,
    month INTEGER,
    
    -- Linkage flags (for reporting)
    has_charter_link BOOLEAN DEFAULT FALSE,
    has_employee_link BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    
    CONSTRAINT unique_driver_payroll_adjustment UNIQUE (driver_payroll_id)
);

-- Add index for reporting
CREATE INDEX IF NOT EXISTS idx_payroll_adjustments_type ON payroll_adjustments(adjustment_type);
CREATE INDEX IF NOT EXISTS idx_payroll_adjustments_date ON payroll_adjustments(original_pay_date);

-- Add payroll_class column to driver_payroll for filtering (optional alternative to separate table)
-- This allows keeping data in driver_payroll but marking it as non-wage
ALTER TABLE driver_payroll ADD COLUMN IF NOT EXISTS payroll_class VARCHAR(50) DEFAULT 'WAGE';
CREATE INDEX IF NOT EXISTS idx_driver_payroll_class ON driver_payroll(payroll_class);

COMMENT ON TABLE payroll_adjustments IS 'Segregated payroll adjustments (reconciliations, corrections) excluded from wage KPIs';
COMMENT ON COLUMN driver_payroll.payroll_class IS 'WAGE (default) or ADJUSTMENT - filter WAGE for pure payroll analytics';
