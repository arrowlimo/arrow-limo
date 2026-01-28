-- Float Activity Logging and Reconciliation Enhancement
-- Purpose: Add activity logging and enhance float tracking system
-- Created: October 21, 2025

-- Float Activity Log Table
CREATE TABLE IF NOT EXISTS float_activity_log (
    log_id SERIAL PRIMARY KEY,
    float_id INTEGER REFERENCES chauffeur_float_tracking(id),
    activity_type VARCHAR(50) NOT NULL, -- 'float_issued', 'receipt_added', 'reconciled', 'reimbursement', 'charter_integrated'
    description TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB -- For storing additional activity-specific data
);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_float_activity_log_float_id ON float_activity_log(float_id);
CREATE INDEX IF NOT EXISTS idx_float_activity_log_activity_type ON float_activity_log(activity_type);
CREATE INDEX IF NOT EXISTS idx_float_activity_log_created_at ON float_activity_log(created_at);

-- Add banking transaction linkage to chauffeur_float_tracking if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'chauffeur_float_tracking' 
                   AND column_name = 'banking_transaction_id') THEN
        ALTER TABLE chauffeur_float_tracking 
        ADD COLUMN banking_transaction_id INTEGER REFERENCES banking_transactions(transaction_id);
        
        -- Add index for banking reconciliation
        CREATE INDEX idx_chauffeur_float_banking_transaction 
        ON chauffeur_float_tracking(banking_transaction_id);
    END IF;
END $$;

-- Add receipt tracking columns if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'chauffeur_float_tracking' 
                   AND column_name = 'receipt_date') THEN
        ALTER TABLE chauffeur_float_tracking 
        ADD COLUMN receipt_date DATE,
        ADD COLUMN vendor_name VARCHAR(200),
        ADD COLUMN receipt_reference VARCHAR(100);
    END IF;
END $$;

-- Float Management Views
CREATE OR REPLACE VIEW float_dashboard_summary AS
SELECT 
    -- Outstanding Floats
    COALESCE(SUM(CASE WHEN reconciliation_status IN ('pending', 'partial', 'overdue', 'outstanding') 
                      THEN ABS(float_amount) ELSE 0 END), 0) as outstanding_floats,
    COUNT(CASE WHEN reconciliation_status IN ('pending', 'partial', 'overdue', 'outstanding') THEN 1 END) as outstanding_count,
    
    -- Today's Activity
    COALESCE(SUM(CASE WHEN float_date = CURRENT_DATE AND float_amount < 0 
                      THEN ABS(float_amount) ELSE 0 END), 0) as issued_today,
    COUNT(CASE WHEN float_date = CURRENT_DATE AND float_amount < 0 THEN 1 END) as issued_count_today,
    
    -- Reconciled Today
    COALESCE(SUM(CASE WHEN DATE(updated_at) = CURRENT_DATE AND reconciliation_status = 'reconciled' 
                      THEN collection_amount ELSE 0 END), 0) as reconciled_today,
    COUNT(CASE WHEN DATE(updated_at) = CURRENT_DATE AND reconciliation_status = 'reconciled' THEN 1 END) as reconciled_count_today,
    
    -- Pending Reimbursements
    COALESCE(SUM(CASE WHEN collection_amount > ABS(float_amount) AND reconciliation_status != 'reimbursed' 
                      THEN collection_amount - ABS(float_amount) ELSE 0 END), 0) as pending_reimbursements,
    COUNT(CASE WHEN collection_amount > ABS(float_amount) AND reconciliation_status != 'reimbursed' THEN 1 END) as pending_reimbursement_count,
    
    -- Performance Metrics
    AVG(CASE WHEN reconciliation_status = 'reconciled' AND updated_at IS NOT NULL AND float_date IS NOT NULL
             THEN DATE_PART('day', updated_at - float_date) END) as avg_reconciliation_days,
    (COUNT(CASE WHEN reconciliation_status = 'reconciled' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)) as reconciliation_rate
FROM chauffeur_float_tracking
WHERE float_date >= CURRENT_DATE - INTERVAL '12 months';

-- Active Floats with Enhanced Details
CREATE OR REPLACE VIEW active_floats_detailed AS
SELECT 
    cft.id as float_id,
    cft.driver_id,
    cft.driver_name,
    cft.float_amount,
    cft.float_date,
    cft.float_type,
    cft.reserve_number,
    cft.collection_amount,
    cft.reconciliation_status,
    cft.notes,
    cft.payment_method,
    cft.receipt_date,
    cft.vendor_name,
    cft.receipt_reference,
    CASE WHEN cft.float_date IS NOT NULL THEN (CURRENT_DATE - cft.float_date) ELSE 0 END as days_outstanding,
    
    -- Charter Information
    c.charter_date,
    c.pickup_address,
    c.dropoff_address,
    c.driver_total_expense,
    
    -- Employee Information  
    e.full_name as employee_name,
    e.employee_number,
    e.status as employee_status,
    
    -- Banking Integration
    bt.transaction_date as banking_date,
    bt.description as banking_description,
    bt.debit_amount as banking_debit,
    bt.credit_amount as banking_credit,
    
    -- Recent Activity
    (SELECT activity_type FROM float_activity_log fal 
     WHERE fal.float_id = cft.id 
     ORDER BY created_at DESC LIMIT 1) as last_activity,
    (SELECT created_at FROM float_activity_log fal 
     WHERE fal.float_id = cft.id 
     ORDER BY created_at DESC LIMIT 1) as last_activity_date
     
FROM chauffeur_float_tracking cft
LEFT JOIN charters c ON cft.reserve_number = c.reserve_number
LEFT JOIN employees e ON cft.driver_id::text = e.employee_number
LEFT JOIN banking_transactions bt ON cft.banking_transaction_id = bt.transaction_id
WHERE cft.reconciliation_status IN ('pending', 'partial', 'overdue', 'outstanding')
ORDER BY cft.float_date DESC, cft.driver_name;

-- Driver Float Summary
CREATE OR REPLACE VIEW driver_float_summary AS
SELECT 
    cft.driver_id,
    cft.driver_name,
    e.full_name as employee_name,
    e.employee_number,
    e.status as employee_status,
    
    -- Outstanding amounts
    COALESCE(SUM(CASE WHEN cft.reconciliation_status IN ('pending', 'partial', 'overdue', 'outstanding') 
                      THEN ABS(cft.float_amount) ELSE 0 END), 0) as outstanding_amount,
    COUNT(CASE WHEN cft.reconciliation_status IN ('pending', 'partial', 'overdue', 'outstanding') THEN 1 END) as outstanding_count,
    
    -- Monthly activity
    COALESCE(SUM(CASE WHEN cft.float_date >= DATE_TRUNC('month', CURRENT_DATE) 
                      THEN ABS(cft.float_amount) ELSE 0 END), 0) as monthly_floats,
    COUNT(CASE WHEN cft.float_date >= DATE_TRUNC('month', CURRENT_DATE) THEN 1 END) as monthly_count,
    
    -- Performance metrics
    COUNT(*) as total_floats,
    AVG(CASE WHEN cft.reconciliation_status = 'reconciled' AND cft.updated_at IS NOT NULL AND cft.float_date IS NOT NULL
             THEN DATE_PART('day', cft.updated_at - cft.float_date) END) as avg_reconciliation_days,
    (COUNT(CASE WHEN cft.reconciliation_status = 'reconciled' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)) as reconciliation_rate,
    
    -- Latest activity
    MAX(cft.float_date) as last_float_date,
    MAX(cft.updated_at) as last_activity_date
    
FROM chauffeur_float_tracking cft
LEFT JOIN employees e ON cft.driver_id::text = e.employee_number
WHERE cft.float_date >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY cft.driver_id, cft.driver_name, e.full_name, e.employee_number, e.status
ORDER BY outstanding_amount DESC, cft.driver_name;

-- Monthly Float Trends
CREATE OR REPLACE VIEW monthly_float_trends AS
SELECT 
    DATE_TRUNC('month', float_date) as month,
    TO_CHAR(float_date, 'YYYY-MM') as month_text,
    COUNT(*) as float_count,
    SUM(ABS(float_amount)) as total_amount,
    AVG(ABS(float_amount)) as avg_amount,
    COUNT(CASE WHEN reconciliation_status = 'reconciled' THEN 1 END) as reconciled_count,
    (COUNT(CASE WHEN reconciliation_status = 'reconciled' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)) as reconciliation_rate
FROM chauffeur_float_tracking
WHERE float_date >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY DATE_TRUNC('month', float_date), TO_CHAR(float_date, 'YYYY-MM')
ORDER BY month;

-- Grant permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON float_activity_log TO postgres;
GRANT USAGE, SELECT ON SEQUENCE float_activity_log_log_id_seq TO postgres;
GRANT SELECT ON float_dashboard_summary, active_floats_detailed, driver_float_summary, monthly_float_trends TO postgres;

-- Create sample activity log entries for recent floats
INSERT INTO float_activity_log (float_id, activity_type, description, created_by, created_at)
SELECT 
    id,
    'float_issued',
    CONCAT('$', ABS(float_amount), ' float issued via ', COALESCE(payment_method, 'etransfer')),
    'system_migration',
    float_date
FROM chauffeur_float_tracking
WHERE float_date >= CURRENT_DATE - INTERVAL '30 days'
  AND float_amount < 0
ON CONFLICT DO NOTHING;

-- Update reconciliation status for overdue floats
UPDATE chauffeur_float_tracking 
SET reconciliation_status = 'overdue',
    updated_at = CURRENT_TIMESTAMP
WHERE reconciliation_status IN ('pending', 'outstanding') 
  AND float_date < CURRENT_DATE - INTERVAL '7 days';

COMMIT;

-- Summary output
DO $$
DECLARE
    total_floats INTEGER;
    active_floats INTEGER;
    overdue_floats INTEGER;
    reconciled_floats INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_floats FROM chauffeur_float_tracking;
    SELECT COUNT(*) INTO active_floats FROM chauffeur_float_tracking WHERE reconciliation_status IN ('pending', 'partial');
    SELECT COUNT(*) INTO overdue_floats FROM chauffeur_float_tracking WHERE reconciliation_status = 'overdue';
    SELECT COUNT(*) INTO reconciled_floats FROM chauffeur_float_tracking WHERE reconciliation_status = 'reconciled';
    
    RAISE NOTICE '';
    RAISE NOTICE '=== Float Management System Enhancement Complete ===';
    RAISE NOTICE 'Total Floats: %', total_floats;
    RAISE NOTICE 'Active Floats: %', active_floats;
    RAISE NOTICE 'Overdue Floats: %', overdue_floats;
    RAISE NOTICE 'Reconciled Floats: %', reconciled_floats;
    RAISE NOTICE '';
    RAISE NOTICE 'New Tables Created:';
    RAISE NOTICE '  - float_activity_log (activity tracking)';
    RAISE NOTICE '';
    RAISE NOTICE 'Enhanced Tables:';
    RAISE NOTICE '  - chauffeur_float_tracking (banking/receipt integration)';
    RAISE NOTICE '';
    RAISE NOTICE 'New Views Created:';
    RAISE NOTICE '  - float_dashboard_summary (key metrics)';
    RAISE NOTICE '  - active_floats_detailed (comprehensive float details)';
    RAISE NOTICE '  - driver_float_summary (driver performance)';
    RAISE NOTICE '  - monthly_float_trends (trend analysis)';
    RAISE NOTICE '';
    RAISE NOTICE '✅ Float Management API ready for integration';
END $$;