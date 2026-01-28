-- Vehicle loan and lease tracking schema
-- Supports loans, leases, buyouts with full payment history and audit trail

-- Main vehicle loans/leases table
CREATE TABLE IF NOT EXISTS vehicle_loans (
    loan_id SERIAL PRIMARY KEY,
    vin VARCHAR(17),
    vehicle_year INTEGER,
    make_model TEXT,
    agreement_type VARCHAR(20) CHECK (agreement_type IN ('lease', 'loan', 'purchase', 'buyout')),
    dealer_lender TEXT,
    date_signed DATE,
    
    -- Financial terms
    principal_amount NUMERIC(12,2),
    down_payment NUMERIC(12,2),
    monthly_payment NUMERIC(12,2),
    term_months INTEGER,
    interest_rate NUMERIC(5,3), -- store as decimal (e.g., 5.25 for 5.25%)
    
    -- Current status
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'paid_off', 'defaulted', 'transferred')),
    current_balance NUMERIC(12,2),
    total_paid NUMERIC(12,2) DEFAULT 0,
    total_interest_paid NUMERIC(12,2) DEFAULT 0,
    total_fees NUMERIC(12,2) DEFAULT 0,
    nsf_count INTEGER DEFAULT 0,
    
    -- Audit trail
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    source_file TEXT, -- original agreement document path
    
    UNIQUE(vin, date_signed, agreement_type)
);

-- Payment history for vehicle loans
CREATE TABLE IF NOT EXISTS loan_payments (
    payment_id SERIAL PRIMARY KEY,
    loan_id INTEGER REFERENCES vehicle_loans(loan_id),
    payment_date DATE NOT NULL,
    amount NUMERIC(12,2) NOT NULL,
    
    -- Payment breakdown
    principal_portion NUMERIC(12,2),
    interest_portion NUMERIC(12,2),
    fee_amount NUMERIC(12,2) DEFAULT 0,
    fee_type VARCHAR(50), -- 'nsf', 'late_fee', 'processing', etc.
    
    -- Payment source tracking
    receipt_id INTEGER, -- link to receipts table
    banking_transaction_id INTEGER, -- link to banking_transactions
    payment_method VARCHAR(50), -- 'eft', 'check', 'cash', 'credit_card'
    reference_number TEXT,
    
    -- Status and notes
    status VARCHAR(20) DEFAULT 'cleared' CHECK (status IN ('pending', 'cleared', 'bounced', 'reversed')),
    notes TEXT,
    
    created_at TIMESTAMP DEFAULT now(),
    source_file TEXT -- payment confirmation document
);

-- Vehicle documents management
CREATE TABLE IF NOT EXISTS vehicle_documents (
    document_id SERIAL PRIMARY KEY,
    vin VARCHAR(17),
    loan_id INTEGER REFERENCES vehicle_loans(loan_id),
    
    -- File information
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_type VARCHAR(10), -- 'pdf', 'docx', 'xlsx', 'jpg', etc.
    file_size BIGINT,
    file_hash VARCHAR(64), -- sha256 for duplicate detection
    
    -- Document classification
    document_category VARCHAR(50), -- 'agreement', 'payment', 'insurance', 'registration', 'inspection'
    document_type VARCHAR(50), -- 'lease_agreement', 'purchase_agreement', 'payment_confirmation', etc.
    document_date DATE,
    
    -- Thumbnail and metadata
    thumbnail_path TEXT, -- path to generated thumbnail
    extracted_text TEXT, -- searchable text content
    metadata JSONB, -- extracted structured data (amounts, dates, etc.)
    
    created_at TIMESTAMP DEFAULT now(),
    
    UNIQUE(file_hash) -- prevent duplicate files
);

-- Source deductions tracking (for driver pay integration)
CREATE TABLE IF NOT EXISTS source_deductions (
    deduction_id SERIAL PRIMARY KEY,
    driver_id INTEGER, -- link to drivers table
    pay_period_start DATE,
    pay_period_end DATE,
    
    -- Deduction details
    deduction_type VARCHAR(50), -- 'vehicle_payment', 'insurance', 'fuel', 'maintenance', 'other'
    description TEXT,
    amount NUMERIC(12,2),
    
    -- Links to source transactions
    loan_payment_id INTEGER REFERENCES loan_payments(payment_id),
    receipt_id INTEGER, -- link to receipts for fuel/maintenance
    
    -- Payroll integration
    payroll_batch_id INTEGER,
    pay_stub_reference TEXT,
    
    created_at TIMESTAMP DEFAULT now(),
    source_file TEXT
);

-- Update triggers to maintain current_balance and totals
CREATE OR REPLACE FUNCTION update_loan_balances() RETURNS TRIGGER AS $$
BEGIN
    -- Recalculate totals for the affected loan
    UPDATE vehicle_loans SET
        total_paid = (
            SELECT COALESCE(SUM(amount), 0) 
            FROM loan_payments 
            WHERE loan_id = COALESCE(NEW.loan_id, OLD.loan_id) 
            AND status = 'cleared'
        ),
        total_interest_paid = (
            SELECT COALESCE(SUM(interest_portion), 0) 
            FROM loan_payments 
            WHERE loan_id = COALESCE(NEW.loan_id, OLD.loan_id) 
            AND status = 'cleared'
        ),
        total_fees = (
            SELECT COALESCE(SUM(fee_amount), 0) 
            FROM loan_payments 
            WHERE loan_id = COALESCE(NEW.loan_id, OLD.loan_id) 
            AND status = 'cleared'
        ),
        nsf_count = (
            SELECT COUNT(*) 
            FROM loan_payments 
            WHERE loan_id = COALESCE(NEW.loan_id, OLD.loan_id) 
            AND fee_type = 'nsf'
        ),
        current_balance = GREATEST(0, 
            principal_amount - (
                SELECT COALESCE(SUM(principal_portion), 0) 
                FROM loan_payments 
                WHERE loan_id = COALESCE(NEW.loan_id, OLD.loan_id) 
                AND status = 'cleared'
            )
        ),
        updated_at = now()
    WHERE loan_id = COALESCE(NEW.loan_id, OLD.loan_id);
    
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Trigger for payment changes
DROP TRIGGER IF EXISTS trg_update_loan_balances ON loan_payments;
CREATE TRIGGER trg_update_loan_balances
    AFTER INSERT OR UPDATE OR DELETE ON loan_payments
    FOR EACH ROW
    EXECUTE FUNCTION update_loan_balances();

-- Views for reporting

-- Loan summary view
CREATE OR REPLACE VIEW v_loan_summary AS
SELECT 
    vl.*,
    CASE 
        WHEN vl.current_balance <= 0 THEN 'paid_off'
        WHEN vl.current_balance > 0 AND vl.status = 'active' THEN 'active'
        ELSE vl.status
    END as calculated_status,
    
    -- Payment statistics
    (SELECT COUNT(*) FROM loan_payments WHERE loan_id = vl.loan_id AND status = 'cleared') as payments_made,
    (SELECT MAX(payment_date) FROM loan_payments WHERE loan_id = vl.loan_id AND status = 'cleared') as last_payment_date,
    
    -- Remaining terms
    CASE 
        WHEN vl.monthly_payment > 0 AND vl.current_balance > 0 
        THEN CEILING(vl.current_balance / vl.monthly_payment)
        ELSE 0 
    END as estimated_payments_remaining
    
FROM vehicle_loans vl;

-- Payment history view with running balance
CREATE OR REPLACE VIEW v_payment_history AS
SELECT 
    lp.*,
    vl.vin,
    vl.make_model,
    vl.agreement_type,
    
    -- Running balance calculation
    vl.principal_amount - SUM(COALESCE(lp2.principal_portion, 0)) 
    OVER (PARTITION BY lp.loan_id ORDER BY lp.payment_date, lp.payment_id) as balance_after_payment
    
FROM loan_payments lp
JOIN vehicle_loans vl ON lp.loan_id = vl.loan_id
LEFT JOIN loan_payments lp2 ON lp2.loan_id = lp.loan_id 
    AND lp2.payment_date <= lp.payment_date 
    AND lp2.payment_id <= lp.payment_id
    AND lp2.status = 'cleared'
WHERE lp.status = 'cleared';

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_vehicle_loans_vin ON vehicle_loans(vin);
CREATE INDEX IF NOT EXISTS idx_vehicle_loans_status ON vehicle_loans(status);
CREATE INDEX IF NOT EXISTS idx_vehicle_loans_date_signed ON vehicle_loans(date_signed);

CREATE INDEX IF NOT EXISTS idx_loan_payments_loan_date ON loan_payments(loan_id, payment_date);
CREATE INDEX IF NOT EXISTS idx_loan_payments_receipt ON loan_payments(receipt_id);
CREATE INDEX IF NOT EXISTS idx_loan_payments_banking ON loan_payments(banking_transaction_id);

CREATE INDEX IF NOT EXISTS idx_vehicle_docs_vin ON vehicle_documents(vin);
CREATE INDEX IF NOT EXISTS idx_vehicle_docs_category ON vehicle_documents(document_category);
CREATE INDEX IF NOT EXISTS idx_vehicle_docs_date ON vehicle_documents(document_date);

CREATE INDEX IF NOT EXISTS idx_source_deductions_driver_period ON source_deductions(driver_id, pay_period_start, pay_period_end);
CREATE INDEX IF NOT EXISTS idx_source_deductions_type ON source_deductions(deduction_type);