-- Global System Payment Processor Audit & Charter Reconciliation Table
-- Purpose: Separate tracking for VCARD/MCARD/Global System payments and returns
-- Prevents duplication: Reconciliation data (this) vs Expense data (receipts)
-- Models: CC Reader and POS system deposits, fees, refunds, returns

CREATE TABLE IF NOT EXISTS global_system_audit (
    -- Primary Key
    global_audit_id BIGSERIAL PRIMARY KEY,
    
    -- SOURCE IDENTIFIERS
    global_transaction_id VARCHAR(255) UNIQUE NOT NULL,  -- VCARD, MCARD, or system reference
    processor_batch_id VARCHAR(100),  -- Daily/batch reconciliation ID from Global System
    processor_reference VARCHAR(255),  -- Transaction reference from Global System
    
    -- PROCESSOR DETAILS
    processor_name VARCHAR(100) NOT NULL,  -- 'GLOBAL_SYSTEM', 'VCARD', 'MCARD', 'ACARD', 'DCARD', etc.
    card_type VARCHAR(50),  -- 'VCARD', 'MCARD', 'ACARD', 'DCARD', 'VISA', 'MASTERCARD', 'OTHER'
    reader_id VARCHAR(100),  -- Physical reader/terminal ID if available
    
    -- CHARTER LINKAGE (Critical for reconciliation)
    charter_reserve_number VARCHAR(50),
    charter_id BIGINT,
    FOREIGN KEY (charter_id) REFERENCES charters(charter_id) ON DELETE SET NULL,
    
    -- PAYMENT TABLE LINKAGE
    payment_id BIGINT,
    FOREIGN KEY (payment_id) REFERENCES payments(payment_id) ON DELETE SET NULL,
    
    -- CUSTOMER INFO (minimal - Global System doesn't provide much)
    customer_name VARCHAR(255),
    customer_email VARCHAR(255),
    customer_phone VARCHAR(20),
    
    -- TRANSACTION DIRECTION (Critical for balance reconciliation)
    transaction_direction VARCHAR(20) NOT NULL,  -- 'DEPOSIT' (credit/+ balance) or 'WITHDRAWAL' (debit/- balance)
    
    -- TRANSACTION AMOUNTS (in cents)
    -- Note: Global System typically only provides balance/net amounts
    transaction_amount_cents BIGINT NOT NULL,  -- Absolute amount (always positive)
    processing_fee_cents BIGINT DEFAULT 0,
    return_refund_amount_cents BIGINT DEFAULT 0,
    chargeback_amount_cents BIGINT DEFAULT 0,
    adjustment_amount_cents BIGINT DEFAULT 0,
    
    -- BALANCE IMPACT (signed: + for deposits, - for withdrawals/fees)
    balance_impact_cents BIGINT GENERATED ALWAYS AS (
        CASE 
            WHEN transaction_direction = 'DEPOSIT' THEN 
                transaction_amount_cents - processing_fee_cents - return_refund_amount_cents - chargeback_amount_cents + adjustment_amount_cents
            WHEN transaction_direction = 'WITHDRAWAL' THEN 
                -(transaction_amount_cents + processing_fee_cents + return_refund_amount_cents + chargeback_amount_cents - adjustment_amount_cents)
            ELSE 0
        END
    ) STORED,
    
    -- NET AMOUNT RECEIVED (historical, for backwards compatibility)
    net_received_cents BIGINT GENERATED ALWAYS AS (
        transaction_amount_cents - processing_fee_cents - return_refund_amount_cents - chargeback_amount_cents + adjustment_amount_cents
    ) STORED,
    
    -- TRANSACTION TYPE
    transaction_type VARCHAR(50) NOT NULL,  -- 'DEPOSIT', 'PURCHASE', 'REFUND', 'RETURN', 'FEE', 'ADJUSTMENT', 'CHARGEBACK'
    
    -- REFUND/RETURN TRACKING
    is_return_or_refund BOOLEAN DEFAULT FALSE,
    return_refund_reason VARCHAR(500),
    return_refund_date TIMESTAMP,
    return_refund_status VARCHAR(50),  -- 'PENDING', 'PROCESSED', 'PARTIAL', 'DENIED'
    original_transaction_id VARCHAR(255),  -- Links refund back to original VCARD DEPOSIT
    
    -- CHARGEBACK/DISPUTE TRACKING
    has_chargeback BOOLEAN DEFAULT FALSE,
    chargeback_reason VARCHAR(255),
    chargeback_status VARCHAR(50),  -- 'WON', 'LOST', 'PENDING', 'EVIDENCE_NEEDED'
    chargeback_filed_date TIMESTAMP,
    chargeback_resolution_date TIMESTAMP,
    
    -- PAYMENT METHOD DETAILS (if available)
    payment_method VARCHAR(50),  -- 'credit_card', 'debit_card', 'other'
    card_last_4 VARCHAR(4),
    card_brand VARCHAR(50),
    
    -- BANKING RECONCILIATION
    banking_transaction_id VARCHAR(255),
    banking_reference VARCHAR(255),
    bank_id VARCHAR(50),
    
    -- AUDIT STATUS
    audit_status VARCHAR(50) DEFAULT 'PENDING',  -- 'PENDING', 'VERIFIED', 'MISMATCH', 'ORPHANED', 'DUPLICATE', 'RESOLVED'
    audit_notes TEXT,
    
    -- MATCH CONFIDENCE & TRACKING
    charter_match_confidence DECIMAL(3, 2) DEFAULT 0.00,  -- 0.00 to 1.00
    match_method VARCHAR(100),  -- 'EXACT_AMOUNT', 'FUZZY_MATCH', 'MANUAL', 'AUTO_MAP', 'UNMATCHED'
    matched_by_user_id BIGINT,
    match_verified_date TIMESTAMP,
    
    -- SYNC & AUDIT TRAIL
    synced_to_charter BOOLEAN DEFAULT FALSE,
    synced_to_payments BOOLEAN DEFAULT FALSE,
    synced_timestamp TIMESTAMP,
    last_audit_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- METADATA
    data_extraction_batch_id VARCHAR(100),  -- Links to extraction date from Global System
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- CONSTRAINTS
    CHECK (transaction_amount_cents >= 0),
    CHECK (processing_fee_cents >= 0),
    CHECK (return_refund_amount_cents >= 0),
    CHECK (chargeback_amount_cents >= 0),
    CONSTRAINT valid_transaction_type CHECK (transaction_type IN ('DEPOSIT', 'PURCHASE', 'REFUND', 'RETURN', 'FEE', 'ADJUSTMENT', 'CHARGEBACK')),
    CONSTRAINT valid_audit_status CHECK (audit_status IN ('PENDING', 'VERIFIED', 'MISMATCH', 'ORPHANED', 'DUPLICATE', 'RESOLVED')),
    CONSTRAINT valid_transaction_direction CHECK (transaction_direction IN ('DEPOSIT', 'WITHDRAWAL')),
    CONSTRAINT refund_consistency CHECK (
        (is_return_or_refund = FALSE AND return_refund_amount_cents = 0) OR
        (is_return_or_refund = TRUE AND return_refund_amount_cents > 0)
    )
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_global_audit_processor ON global_system_audit(processor_name, card_type);
CREATE INDEX IF NOT EXISTS idx_global_audit_charter ON global_system_audit(charter_reserve_number, charter_id);
CREATE INDEX IF NOT EXISTS idx_global_audit_payment ON global_system_audit(payment_id, global_transaction_id);
CREATE INDEX IF NOT EXISTS idx_global_audit_status ON global_system_audit(audit_status, match_verified_date);
CREATE INDEX IF NOT EXISTS idx_global_audit_dates ON global_system_audit(created_at, data_extraction_batch_id);
CREATE INDEX IF NOT EXISTS idx_global_audit_returns ON global_system_audit(is_return_or_refund, return_refund_status);
CREATE INDEX IF NOT EXISTS idx_global_audit_chargebacks ON global_system_audit(has_chargeback, chargeback_status);
CREATE INDEX IF NOT EXISTS idx_global_audit_amounts ON global_system_audit(transaction_amount_cents, net_received_cents, processing_fee_cents);
CREATE INDEX IF NOT EXISTS idx_global_audit_banking ON global_system_audit(banking_transaction_id, bank_id);

-- View for quick dashboard/verification
CREATE OR REPLACE VIEW global_system_audit_summary AS
SELECT
    COUNT(*) as total_transactions,
    SUM(transaction_amount_cents) / 100.00 as total_gross_amount,
    SUM(balance_impact_cents) / 100.00 as net_balance_impact,
    SUM(CASE WHEN transaction_direction = 'DEPOSIT' THEN transaction_amount_cents ELSE 0 END) / 100.00 as total_deposits,
    SUM(CASE WHEN transaction_direction = 'WITHDRAWAL' THEN transaction_amount_cents ELSE 0 END) / 100.00 as total_withdrawals,
    SUM(processing_fee_cents) / 100.00 as total_fees,
    SUM(CASE WHEN is_return_or_refund THEN return_refund_amount_cents ELSE 0 END) / 100.00 as total_returns,
    COUNT(CASE WHEN audit_status = 'VERIFIED' THEN 1 END) as verified_count,
    COUNT(CASE WHEN audit_status = 'PENDING' THEN 1 END) as pending_count,
    COUNT(CASE WHEN charter_id IS NOT NULL THEN 1 END) as charter_linked_count,
    COUNT(CASE WHEN charter_id IS NULL THEN 1 END) as charter_unlinked_count,
    processor_name,
    card_type
FROM global_system_audit
GROUP BY processor_name, card_type;

-- View for returns/refunds analysis
CREATE OR REPLACE VIEW global_system_returns_analysis AS
SELECT
    global_audit_id,
    processor_name,
    card_type,
    created_at,
    original_transaction_id,
    transaction_amount_cents / 100.00 as original_amount,
    return_refund_amount_cents / 100.00 as refund_amount,
    return_refund_reason,
    return_refund_status,
    charter_reserve_number,
    charter_id,
    audit_status,
    days_since_refund = ROUND(EXTRACT(DAY FROM (CURRENT_TIMESTAMP - return_refund_date)))
FROM global_system_audit
WHERE is_return_or_refund = TRUE
ORDER BY return_refund_date DESC;

-- View for reconciliation status
CREATE OR REPLACE VIEW global_system_reconciliation_status AS
SELECT
    processor_name,
    card_type,
    transaction_type,
    transaction_direction,
    COUNT(*) as transaction_count,
    SUM(transaction_amount_cents) / 100.00 as total_amount,
    SUM(balance_impact_cents) / 100.00 as balance_impact,
    COUNT(CASE WHEN charter_id IS NOT NULL THEN 1 END) as linked_to_charter,
    COUNT(CASE WHEN banking_transaction_id IS NOT NULL THEN 1 END) as linked_to_banking,
    COUNT(CASE WHEN audit_status = 'VERIFIED' THEN 1 END) as verified,
    COUNT(CASE WHEN audit_status = 'PENDING' THEN 1 END) as pending,
    COUNT(CASE WHEN audit_status = 'MISMATCH' THEN 1 END) as mismatched
FROM global_system_audit
GROUP BY processor_name, card_type, transaction_type, transaction_direction
ORDER BY processor_name, card_type, transaction_type, transaction_direction;

COMMENT ON TABLE global_system_audit IS 'Tracks Global System payment processor transactions (VCARD, MCARD, ACARD, DCARD) separately from receipts to prevent duplication. All transactions tracked with deposit vs withdrawal direction for balance reconciliation. Covers deposits, fees, returns, chargebacks, and reconciliation status.';

COMMENT ON COLUMN global_system_audit.processor_name IS 'Payment processor identifier (GLOBAL_SYSTEM, VCARD, MCARD, ACARD, DCARD)';
COMMENT ON COLUMN global_system_audit.original_transaction_id IS 'Links refund transactions back to original VCARD/MCARD DEPOSIT for full reconciliation';
COMMENT ON COLUMN global_system_audit.has_chargeback IS 'Customer dispute/chargeback flag';
COMMENT ON COLUMN global_system_audit.audit_status IS 'Verification status: PENDING (new), VERIFIED (matched to charter), MISMATCH (amount/date issues), ORPHANED (no charter match), DUPLICATE (duplicate entry), RESOLVED (all issues fixed)';
