-- CIBC Business Card Management System
-- Migration to create CIBC card management tables
-- Paul Heffner's 3 CIBC Business Cards: Business ($25k), Personal ($15k), Salary ($10k)

-- Drop existing tables if they exist (for clean deployment)
DROP TABLE IF EXISTS cibc_card_transactions CASCADE;
DROP TABLE IF EXISTS cibc_business_cards CASCADE;

-- CIBC Business Cards table (Paul's 3 cards)
CREATE TABLE cibc_business_cards (
    card_id SERIAL PRIMARY KEY,
    card_name VARCHAR(100) NOT NULL,
    card_type VARCHAR(50) NOT NULL,
    card_number_last4 VARCHAR(4),
    credit_limit DECIMAL(12,2) NOT NULL,
    current_balance DECIMAL(12,2) DEFAULT 0,
    available_credit DECIMAL(12,2),
    statement_date DATE,
    payment_due_date DATE,
    minimum_payment DECIMAL(12,2) DEFAULT 0,
    
    -- Link to owner equity account
    owner_equity_account_id INTEGER REFERENCES owner_equity_accounts(equity_account_id),
    
    -- Auto-categorization settings
    auto_categorization_enabled BOOLEAN DEFAULT true,
    default_expense_category VARCHAR(100) DEFAULT 'Business Expenses',
    
    -- Banking integration
    banking_sync_enabled BOOLEAN DEFAULT true,
    last_banking_sync TIMESTAMP,
    
    -- Metadata
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CIBC Card Transactions table
CREATE TABLE cibc_card_transactions (
    transaction_id SERIAL PRIMARY KEY,
    card_id INTEGER REFERENCES cibc_business_cards(card_id),
    
    -- Transaction details
    transaction_date DATE NOT NULL,
    posting_date DATE,
    description TEXT NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    transaction_type VARCHAR(50) DEFAULT 'Purchase',
    
    -- Merchant information
    merchant_name VARCHAR(200),
    merchant_category VARCHAR(100),
    
    -- Categorization
    expense_category VARCHAR(100),
    business_purpose TEXT,
    auto_categorized BOOLEAN DEFAULT false,
    manual_review_required BOOLEAN DEFAULT false,
    
    -- Banking reconciliation
    banking_transaction_id INTEGER REFERENCES banking_transactions(transaction_id),
    reconciled BOOLEAN DEFAULT false,
    reconciled_at TIMESTAMP,
    
    -- Receipt tracking
    receipt_required BOOLEAN DEFAULT false,
    receipt_uploaded BOOLEAN DEFAULT false,
    receipt_path VARCHAR(500),
    
    -- Tax information
    gst_applicable BOOLEAN DEFAULT true,
    gst_amount DECIMAL(12,2) DEFAULT 0,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Auto-update timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_cibc_cards_updated_at 
    BEFORE UPDATE ON cibc_business_cards 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_cibc_transactions_updated_at 
    BEFORE UPDATE ON cibc_card_transactions 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Indexes for performance
CREATE INDEX idx_cibc_cards_equity_account ON cibc_business_cards(owner_equity_account_id);
CREATE INDEX idx_cibc_transactions_card ON cibc_card_transactions(card_id);
CREATE INDEX idx_cibc_transactions_date ON cibc_card_transactions(transaction_date);
CREATE INDEX idx_cibc_transactions_banking ON cibc_card_transactions(banking_transaction_id);
CREATE INDEX idx_cibc_transactions_category ON cibc_card_transactions(expense_category);

-- Insert Paul's 3 CIBC Business Cards
INSERT INTO cibc_business_cards (
    card_name, card_type, card_number_last4, credit_limit, 
    auto_categorization_enabled, default_expense_category
) VALUES 
-- Paul's Business Card ($25,000 limit)
(
    'CIBC Business Visa', 
    'Business', 
    '****', 
    25000.00,
    true,
    'Business Operations'
),
-- Paul's Personal Business Card ($15,000 limit)  
(
    'CIBC Personal Business Visa',
    'Personal Business',
    '****', 
    15000.00,
    true,
    'Owner Personal Expenses'
),
-- Paul's Salary Card ($10,000 limit)
(
    'CIBC Salary Card Visa',
    'Salary',
    '****',
    10000.00,
    true,
    'Owner Salary Equivalent'
);

-- Auto-categorization rules table
CREATE TABLE cibc_auto_categorization_rules (
    rule_id SERIAL PRIMARY KEY,
    card_id INTEGER REFERENCES cibc_business_cards(card_id),
    
    -- Matching criteria
    merchant_pattern VARCHAR(200),
    description_pattern VARCHAR(200),
    amount_min DECIMAL(12,2),
    amount_max DECIMAL(12,2),
    
    -- Categorization result
    expense_category VARCHAR(100) NOT NULL,
    business_purpose VARCHAR(200),
    auto_approve BOOLEAN DEFAULT false,
    
    -- Rule metadata
    rule_priority INTEGER DEFAULT 100,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Common auto-categorization rules
INSERT INTO cibc_auto_categorization_rules (
    card_id, merchant_pattern, expense_category, business_purpose, auto_approve
) VALUES
-- Fuel expenses (all cards)
(1, '%Shell%', 'Vehicle Fuel', 'Business vehicle fuel', true),
(1, '%Petro%', 'Vehicle Fuel', 'Business vehicle fuel', true),
(1, '%Esso%', 'Vehicle Fuel', 'Business vehicle fuel', true),
(2, '%Shell%', 'Vehicle Fuel', 'Vehicle fuel', true),
(2, '%Petro%', 'Vehicle Fuel', 'Vehicle fuel', true),
(3, '%Shell%', 'Vehicle Fuel', 'Vehicle fuel', true),

-- Office supplies
(1, '%Staples%', 'Office Supplies', 'Business office supplies', true),
(1, '%Office Depot%', 'Office Supplies', 'Business office supplies', true),

-- Vehicle maintenance
(1, '%Canadian Tire%', 'Vehicle Maintenance', 'Business vehicle maintenance', false),
(1, '%Jiffy Lube%', 'Vehicle Maintenance', 'Business vehicle maintenance', false),

-- Communication
(1, '%SaskTel%', 'Communication', 'Business phone/internet', true),
(1, '%Rogers%', 'Communication', 'Business communication', true);

-- Monthly summary view
CREATE VIEW v_cibc_monthly_summary AS
SELECT 
    c.card_id,
    c.card_name,
    c.card_type,
    DATE_TRUNC('month', t.transaction_date) as month_year,
    COUNT(t.transaction_id) as transaction_count,
    SUM(t.amount) as total_amount,
    SUM(CASE WHEN t.auto_categorized THEN t.amount ELSE 0 END) as auto_categorized_amount,
    SUM(CASE WHEN t.manual_review_required THEN t.amount ELSE 0 END) as review_required_amount,
    SUM(CASE WHEN t.reconciled THEN t.amount ELSE 0 END) as reconciled_amount,
    COUNT(CASE WHEN t.receipt_required AND NOT t.receipt_uploaded THEN 1 END) as missing_receipts
FROM cibc_business_cards c
LEFT JOIN cibc_card_transactions t ON c.card_id = t.card_id
GROUP BY c.card_id, c.card_name, c.card_type, DATE_TRUNC('month', t.transaction_date)
ORDER BY c.card_id, month_year DESC;

-- Card utilization view
CREATE VIEW v_cibc_card_utilization AS
SELECT 
    c.card_id,
    c.card_name,
    c.card_type,
    c.credit_limit,
    c.current_balance,
    c.available_credit,
    ROUND((c.current_balance / c.credit_limit) * 100, 2) as utilization_percentage,
    CASE 
        WHEN (c.current_balance / c.credit_limit) > 0.9 THEN 'High Risk'
        WHEN (c.current_balance / c.credit_limit) > 0.7 THEN 'Medium Risk'
        ELSE 'Normal'
    END as risk_level
FROM cibc_business_cards c
WHERE c.is_active = true;

-- Reconciliation status view
CREATE VIEW v_cibc_reconciliation_status AS
SELECT 
    c.card_id,
    c.card_name,
    COUNT(t.transaction_id) as total_transactions,
    COUNT(CASE WHEN t.reconciled THEN 1 END) as reconciled_transactions,
    COUNT(CASE WHEN NOT t.reconciled THEN 1 END) as unreconciled_transactions,
    SUM(CASE WHEN NOT t.reconciled THEN t.amount ELSE 0 END) as unreconciled_amount,
    COUNT(CASE WHEN t.manual_review_required THEN 1 END) as review_required_count,
    COUNT(CASE WHEN t.receipt_required AND NOT t.receipt_uploaded THEN 1 END) as missing_receipt_count
FROM cibc_business_cards c
LEFT JOIN cibc_card_transactions t ON c.card_id = t.card_id
WHERE c.is_active = true
GROUP BY c.card_id, c.card_name;

COMMENT ON TABLE cibc_business_cards IS 'Paul Heffner CIBC Business Cards: Business ($25k), Personal ($15k), Salary ($10k)';
COMMENT ON TABLE cibc_card_transactions IS 'CIBC card transactions with auto-categorization and banking reconciliation';
COMMENT ON VIEW v_cibc_monthly_summary IS 'Monthly transaction summary by card';
COMMENT ON VIEW v_cibc_card_utilization IS 'Credit utilization tracking for risk management';
COMMENT ON VIEW v_cibc_reconciliation_status IS 'Banking reconciliation status by card';