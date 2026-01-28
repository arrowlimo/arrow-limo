-- Create charter_credit_ledger table to track client credits from overpayments
-- Purpose: Segregate excess payments for future charter allocation
-- Created: 2025-11-22 after overpayment remediation analysis

CREATE TABLE IF NOT EXISTS charter_credit_ledger (
    credit_id SERIAL PRIMARY KEY,
    source_reserve_number VARCHAR(50) NOT NULL,
    source_charter_id INTEGER REFERENCES charters(charter_id) ON DELETE SET NULL,
    client_id INTEGER REFERENCES clients(client_id) ON DELETE CASCADE,
    credit_amount DECIMAL(12,2) NOT NULL CHECK (credit_amount > 0),
    credit_reason VARCHAR(100) NOT NULL,
    remaining_balance DECIMAL(12,2) NOT NULL CHECK (remaining_balance >= 0 AND remaining_balance <= credit_amount),
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    applied_date TIMESTAMP,
    applied_to_reserve_number VARCHAR(50),
    applied_to_charter_id INTEGER REFERENCES charters(charter_id) ON DELETE SET NULL,
    notes TEXT,
    created_by VARCHAR(100) DEFAULT 'system',
    CONSTRAINT valid_balance CHECK (remaining_balance <= credit_amount)
);

-- Indexes for efficient lookups
CREATE INDEX idx_credit_ledger_source_reserve ON charter_credit_ledger(source_reserve_number);
CREATE INDEX idx_credit_ledger_client ON charter_credit_ledger(client_id);
CREATE INDEX idx_credit_ledger_applied_reserve ON charter_credit_ledger(applied_to_reserve_number);
CREATE INDEX idx_credit_ledger_remaining ON charter_credit_ledger(remaining_balance) WHERE remaining_balance > 0;

-- Comments
COMMENT ON TABLE charter_credit_ledger IS 'Tracks client credits from overpayments and cancelled charter deposits';
COMMENT ON COLUMN charter_credit_ledger.credit_reason IS 'Values: UNIFORM_INSTALLMENT, CANCELLED_RETENTION, ETR_OVERPAY, MULTI_CHARTER_PREPAY, MIXED_OVERPAY';
COMMENT ON COLUMN charter_credit_ledger.remaining_balance IS 'Available credit balance (decreases as applied to future charters)';
COMMENT ON COLUMN charter_credit_ledger.applied_date IS 'When credit was fully exhausted or applied to another charter';
