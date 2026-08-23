-- GST Remittance Payment Tracking
-- Tracks GST payments to CRA from multiple sources:
-- - Manual entries for payments made at other banks
-- - Linked banking transactions
-- - Multi-period GST calculations
-- CRA requires 6-year record retention (Section 230, Income Tax Act)

BEGIN;

-- ============================================================================
-- GST REMITTANCE PAYMENT TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS gst_remittance_payments (
    gst_payment_id BIGSERIAL PRIMARY KEY,
    
    -- Remittance identification
    tax_year INT NOT NULL,
    gst_period_month INT NOT NULL,  -- 1-12, month payment covers
    
    -- Payment details
    gst_amount_collected DECIMAL(12, 2) NOT NULL,  -- Total GST collected in period
    payment_amount DECIMAL(12, 2) NOT NULL,        -- Amount actually remitted to CRA
    payment_date DATE NOT NULL,                    -- Date payment was made to CRA
    
    -- Payment method tracking
    payment_method VARCHAR(50) NOT NULL,  -- 'banking_transaction', 'manual_entry', 'forced_debit'
    banking_institution VARCHAR(100),     -- Bank name if multi-bank (e.g., 'RBC', 'TD', 'BMO')
    reference_number VARCHAR(100),        -- CRA confirmation number, cheque#, wire reference, etc.
    banking_transaction_id BIGINT,        -- Link to banking_transactions table if available
    
    -- Remittance status
    remittance_status VARCHAR(50) NOT NULL DEFAULT 'pending',  
    -- pending: awaiting confirmation
    -- submitted: submitted to CRA
    -- confirmed: CRA has confirmed receipt
    -- reconciled: matched with banking/accounting records
    
    -- Record-keeping
    notes TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- CRA audit trail
    retained_until DATE NOT NULL,  -- 6 years from end of relevant tax year per Income Tax Act
    audit_verified BOOLEAN DEFAULT FALSE,
    audit_verified_by VARCHAR(100),
    audit_verified_date TIMESTAMP,
    
    UNIQUE (tax_year, gst_period_month),
    FOREIGN KEY (banking_transaction_id) REFERENCES banking_transactions(id) ON DELETE SET NULL
);

CREATE INDEX idx_gst_payment_year_month ON gst_remittance_payments(tax_year, gst_period_month);
CREATE INDEX idx_gst_payment_status ON gst_remittance_payments(remittance_status);
CREATE INDEX idx_gst_payment_date ON gst_remittance_payments(payment_date);
CREATE INDEX idx_gst_payment_banking_link ON gst_remittance_payments(banking_transaction_id);
CREATE INDEX idx_gst_payment_retained_until ON gst_remittance_payments(retained_until);

-- ============================================================================
-- GST CALCULATION STAGING TABLE
-- Used to aggregate GST collected by period for remittance
-- ============================================================================
CREATE TABLE IF NOT EXISTS gst_collected_by_period (
    gst_period_id BIGSERIAL PRIMARY KEY,
    tax_year INT NOT NULL,
    gst_period_month INT NOT NULL,
    gst_amount_collected DECIMAL(12, 2) NOT NULL DEFAULT 0,
    receipt_count INT DEFAULT 0,
    last_calculated TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE (tax_year, gst_period_month)
);

CREATE INDEX idx_gst_collected_period ON gst_collected_by_period(tax_year, gst_period_month);

COMMIT;
