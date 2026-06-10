-- Square API Audit & Charter Reconciliation Master Table
-- Purpose: Centralized verification table linking payments to charters
-- Links: Square payments, refunds, disputes, fees to charter reserve numbers

CREATE TABLE IF NOT EXISTS square_api_audit (
    -- Primary Key
    square_audit_id BIGSERIAL PRIMARY KEY,
    
    -- SOURCE IDENTIFIERS
    square_payment_id VARCHAR(255) UNIQUE NOT NULL,
    square_customer_id VARCHAR(255),
    square_refund_id VARCHAR(255),
    square_dispute_id VARCHAR(255),
    
    -- CHARTER LINKAGE (Critical for reconciliation)
    charter_reserve_number VARCHAR(50),
    charter_id BIGINT,
    FOREIGN KEY (charter_id) REFERENCES charters(charter_id) ON DELETE SET NULL,
    
    -- PAYMENT TABLE LINKAGE
    payment_id BIGINT,
    FOREIGN KEY (payment_id) REFERENCES payments(payment_id) ON DELETE SET NULL,
    
    -- CUSTOMER INFO
    customer_name VARCHAR(255),
    customer_email VARCHAR(255),
    customer_phone VARCHAR(20),
    customer_company VARCHAR(255),
    
    -- TRANSACTION AMOUNTS (in cents)
    transaction_amount_cents BIGINT NOT NULL,
    refund_amount_cents BIGINT DEFAULT 0,
    dispute_amount_cents BIGINT DEFAULT 0,
    square_fee_cents BIGINT DEFAULT 0,
    processing_fee_cents BIGINT DEFAULT 0,
    loan_fee_cents BIGINT DEFAULT 0,
    loan_payment_cents BIGINT DEFAULT 0,
    
    -- NET AMOUNT RECEIVED
    net_received_cents BIGINT GENERATED ALWAYS AS (
        transaction_amount_cents - refund_amount_cents - dispute_amount_cents - square_fee_cents - processing_fee_cents
    ) STORED,
    
    -- PAYMENT METHOD & DETAILS
    payment_method VARCHAR(50) NOT NULL, -- 'credit_card', 'debit_card', 'cash', 'check', 'etransfer', etc.
    payment_source_type VARCHAR(100),
    card_brand VARCHAR(50),
    card_last_4 VARCHAR(4),
    
    -- REFUND TRACKING
    has_refund BOOLEAN DEFAULT FALSE,
    refund_reason VARCHAR(500),
    refund_date TIMESTAMP,
    refund_status VARCHAR(50),
    
    -- DISPUTE TRACKING
    has_dispute BOOLEAN DEFAULT FALSE,
    dispute_reason VARCHAR(255),
    dispute_amount_received DECIMAL(10, 2),
    dispute_status VARCHAR(50), -- 'WON', 'LOST', 'PENDING', 'EVIDENCE_NEEDED'
    dispute_created_date TIMESTAMP,
    dispute_evidence_files_count INTEGER DEFAULT 0,
    
    -- LOAN/CAPITAL TRACKING
    has_square_capital_loan BOOLEAN DEFAULT FALSE,
    square_capital_loan_id VARCHAR(255),
    
    -- BANKING RECONCILIATION
    banking_transaction_id VARCHAR(255),
    banking_reference VARCHAR(255),
    etransfer_transaction_id VARCHAR(255),
    check_number VARCHAR(50),
    cash_batch_id VARCHAR(100),
    
    -- AUDIT STATUS
    audit_status VARCHAR(50) DEFAULT 'PENDING', -- 'PENDING', 'VERIFIED', 'MISMATCH', 'ORPHANED', 'DUPLICATE', 'RESOLVED'
    audit_notes TEXT,
    
    -- COMMENTS & REFERENCES
    merchant_notes TEXT,
    customer_notes TEXT,
    reconciliation_notes TEXT,
    internal_reference_codes VARCHAR(500),
    
    -- CROSS-REFERENCE DATA
    linked_payments_count INTEGER DEFAULT 1,
    linked_refunds_count INTEGER DEFAULT 0,
    linked_disputes_count INTEGER DEFAULT 0,
    
    -- SQUARE DATA INTEGRITY
    square_created_timestamp TIMESTAMP NOT NULL,
    square_updated_timestamp TIMESTAMP,
    square_risk_level VARCHAR(50),
    square_receipt_url TEXT,
    
    -- MATCH CONFIDENCE & TRACKING
    charter_match_confidence DECIMAL(3, 2) DEFAULT 0.00, -- 0.00 to 1.00
    match_method VARCHAR(100), -- 'EXACT_AMOUNT', 'FUZZY_MATCH', 'MANUAL', 'AUTO_MAP', 'UNMATCHED'
    matched_by_user_id BIGINT,
    match_verified_date TIMESTAMP,
    
    -- SYNC & AUDIT TRAIL
    synced_to_charter BOOLEAN DEFAULT FALSE,
    synced_to_payments BOOLEAN DEFAULT FALSE,
    synced_timestamp TIMESTAMP,
    last_audit_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- METADATA
    data_extraction_batch_id VARCHAR(100), -- Links to extraction date (e.g., 20260203_115106)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- INDEXES FOR PERFORMANCE
    CHECK (transaction_amount_cents >= 0),
    CHECK (refund_amount_cents >= 0),
    CHECK (dispute_amount_cents >= 0),
    CONSTRAINT valid_audit_status CHECK (audit_status IN ('PENDING', 'VERIFIED', 'MISMATCH', 'ORPHANED', 'DUPLICATE', 'RESOLVED'))
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_square_audit_charter ON square_api_audit(charter_reserve_number, charter_id);
CREATE INDEX IF NOT EXISTS idx_square_audit_payment ON square_api_audit(payment_id, square_payment_id);
CREATE INDEX IF NOT EXISTS idx_square_audit_customer ON square_api_audit(square_customer_id, customer_email);
CREATE INDEX IF NOT EXISTS idx_square_audit_status ON square_api_audit(audit_status, match_verified_date);
CREATE INDEX IF NOT EXISTS idx_square_audit_dates ON square_api_audit(square_created_timestamp, data_extraction_batch_id);
CREATE INDEX IF NOT EXISTS idx_square_audit_reconciliation ON square_api_audit(has_refund, has_dispute, audit_status);
CREATE INDEX IF NOT EXISTS idx_square_audit_amounts ON square_api_audit(transaction_amount_cents, refund_amount_cents, net_received_cents);

-- View for quick dashboard/verification
CREATE OR REPLACE VIEW square_audit_summary AS
SELECT 
    COUNT(*) as total_transactions,
    SUM(transaction_amount_cents) / 100.0 as total_amount,
    SUM(refund_amount_cents) / 100.0 as total_refunded,
    SUM(dispute_amount_cents) / 100.0 as total_disputed,
    SUM(square_fee_cents) / 100.0 as total_square_fees,
    SUM(net_received_cents) / 100.0 as net_received,
    COUNT(CASE WHEN has_refund THEN 1 END) as refund_count,
    COUNT(CASE WHEN has_dispute THEN 1 END) as dispute_count,
    COUNT(CASE WHEN charter_id IS NULL THEN 1 END) as orphaned_count,
    COUNT(CASE WHEN audit_status = 'VERIFIED' THEN 1 END) as verified_count,
    COUNT(CASE WHEN audit_status = 'MISMATCH' THEN 1 END) as mismatch_count,
    COUNT(CASE WHEN dispute_status = 'LOST' THEN 1 END) as lost_disputes
FROM square_api_audit
WHERE data_extraction_batch_id = '20260203_115106';

-- View for orphaned/unmatched transactions
CREATE OR REPLACE VIEW square_orphaned_transactions AS
SELECT 
    square_audit_id,
    square_payment_id,
    customer_name,
    customer_email,
    transaction_amount_cents / 100.0 as amount,
    charter_reserve_number,
    charter_id,
    payment_id,
    audit_status,
    audit_notes,
    square_created_timestamp
FROM square_api_audit
WHERE charter_id IS NULL 
   OR audit_status IN ('ORPHANED', 'MISMATCH', 'DUPLICATE')
ORDER BY transaction_amount_cents DESC;

-- View for dispute tracking
CREATE OR REPLACE VIEW square_disputes_tracking AS
SELECT 
    square_audit_id,
    square_dispute_id,
    charter_reserve_number,
    customer_name,
    dispute_amount_cents / 100.0 as dispute_amount,
    dispute_reason,
    dispute_status,
    dispute_evidence_files_count,
    dispute_created_date,
    audit_status,
    reconciliation_notes
FROM square_api_audit
WHERE has_dispute = TRUE
ORDER BY dispute_created_date DESC;

-- View for refund tracking
CREATE OR REPLACE VIEW square_refunds_tracking AS
SELECT 
    square_audit_id,
    square_refund_id,
    square_payment_id,
    charter_reserve_number,
    customer_name,
    transaction_amount_cents / 100.0 as original_amount,
    refund_amount_cents / 100.0 as refund_amount,
    refund_reason,
    refund_status,
    refund_date,
    audit_status
FROM square_api_audit
WHERE has_refund = TRUE
ORDER BY refund_date DESC;

-- View for charter linkage verification
CREATE OR REPLACE VIEW square_charter_linkage AS
SELECT 
    charter_reserve_number,
    COUNT(*) as payment_count,
    COUNT(DISTINCT square_payment_id) as square_transactions,
    SUM(transaction_amount_cents) / 100.0 as total_billed,
    SUM(refund_amount_cents) / 100.0 as total_refunded,
    SUM(net_received_cents) / 100.0 as net_received,
    COUNT(CASE WHEN audit_status = 'VERIFIED' THEN 1 END) as verified_count,
    COUNT(CASE WHEN audit_status = 'MISMATCH' THEN 1 END) as mismatch_count,
    STRING_AGG(DISTINCT customer_name, ', ') as customers,
    STRING_AGG(DISTINCT audit_status, ', ') as statuses
FROM square_api_audit
WHERE charter_reserve_number IS NOT NULL
GROUP BY charter_reserve_number
ORDER BY total_billed DESC;

-- View for customer payment history
CREATE OR REPLACE VIEW square_customer_payment_history AS
SELECT 
    square_customer_id,
    customer_name,
    customer_email,
    customer_company,
    COUNT(DISTINCT square_payment_id) as total_transactions,
    SUM(transaction_amount_cents) / 100.0 as lifetime_value,
    SUM(refund_amount_cents) / 100.0 as total_refunded,
    COUNT(CASE WHEN has_refund THEN 1 END) as refund_count,
    COUNT(CASE WHEN has_dispute THEN 1 END) as dispute_count,
    COUNT(DISTINCT charter_reserve_number) as charter_count,
    MAX(square_created_timestamp) as last_transaction_date,
    MIN(square_created_timestamp) as first_transaction_date
FROM square_api_audit
GROUP BY square_customer_id, customer_name, customer_email, customer_company
ORDER BY lifetime_value DESC;
