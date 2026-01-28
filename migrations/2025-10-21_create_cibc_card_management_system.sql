-- CIBC Business Card Management System
-- Purpose: Paul Heffner's 3 CIBC business cards for owner equity tracking
-- Created: October 21, 2025

-- CIBC Business Cards Table
CREATE TABLE IF NOT EXISTS cibc_business_cards (
    card_id SERIAL PRIMARY KEY,
    card_name VARCHAR(100) NOT NULL,
    card_type VARCHAR(50) NOT NULL CHECK (card_type IN ('business_expenses', 'personal_allocation', 'salary_equity')),
    last_four_digits VARCHAR(4) NOT NULL,
    credit_limit DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    current_balance DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    owner_equity_account_id INTEGER REFERENCES owner_equity_accounts(account_id),
    default_category VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CIBC Card Transactions Table
CREATE TABLE IF NOT EXISTS cibc_card_transactions (
    transaction_id SERIAL PRIMARY KEY,
    card_id INTEGER NOT NULL REFERENCES cibc_business_cards(card_id),
    transaction_date DATE NOT NULL,
    vendor_name VARCHAR(200),
    amount DECIMAL(12,2) NOT NULL,
    category VARCHAR(100),
    description TEXT,
    receipt_image_path VARCHAR(500),
    banking_transaction_id INTEGER REFERENCES banking_transactions(transaction_id),
    is_business_expense BOOLEAN DEFAULT true,
    tax_deductible BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Prevent duplicate transactions
    UNIQUE(card_id, transaction_date, vendor_name, amount)
);

-- CIBC Statement Uploads Table
CREATE TABLE IF NOT EXISTS cibc_statement_uploads (
    upload_id SERIAL PRIMARY KEY,
    card_id INTEGER NOT NULL REFERENCES cibc_business_cards(card_id),
    filename VARCHAR(200) NOT NULL,
    statement_period DATE NOT NULL,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT false,
    transactions_processed INTEGER DEFAULT 0,
    file_size BIGINT,
    file_hash VARCHAR(64),
    error_message TEXT
);

-- CIBC Categorization Rules Table
CREATE TABLE IF NOT EXISTS cibc_categorization_rules (
    rule_id SERIAL PRIMARY KEY,
    rule_name VARCHAR(100) NOT NULL,
    vendor_pattern VARCHAR(200),
    description_pattern VARCHAR(200),
    amount_min DECIMAL(12,2),
    amount_max DECIMAL(12,2),
    category VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_cibc_cards_type ON cibc_business_cards(card_type);
CREATE INDEX IF NOT EXISTS idx_cibc_cards_active ON cibc_business_cards(is_active);
CREATE INDEX IF NOT EXISTS idx_cibc_cards_equity_account ON cibc_business_cards(owner_equity_account_id);

CREATE INDEX IF NOT EXISTS idx_cibc_transactions_card ON cibc_card_transactions(card_id);
CREATE INDEX IF NOT EXISTS idx_cibc_transactions_date ON cibc_card_transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_cibc_transactions_vendor ON cibc_card_transactions(vendor_name);
CREATE INDEX IF NOT EXISTS idx_cibc_transactions_category ON cibc_card_transactions(category);
CREATE INDEX IF NOT EXISTS idx_cibc_transactions_banking ON cibc_card_transactions(banking_transaction_id);

CREATE INDEX IF NOT EXISTS idx_cibc_uploads_card ON cibc_statement_uploads(card_id);
CREATE INDEX IF NOT EXISTS idx_cibc_uploads_period ON cibc_statement_uploads(statement_period);

CREATE INDEX IF NOT EXISTS idx_cibc_rules_active ON cibc_categorization_rules(is_active, priority);

-- Create Paul's default CIBC business cards
DO $$
DECLARE
    business_account_id INTEGER;
    personal_account_id INTEGER;
    salary_account_id INTEGER;
BEGIN
    -- Get Paul's owner equity account IDs
    SELECT account_id INTO business_account_id 
    FROM owner_equity_accounts 
    WHERE account_name = 'Paul Business Expenses' AND account_type = 'business_expenses';
    
    SELECT account_id INTO personal_account_id
    FROM owner_equity_accounts 
    WHERE account_name = 'Paul Personal Allocation' AND account_type = 'personal_allocation';
    
    SELECT account_id INTO salary_account_id
    FROM owner_equity_accounts 
    WHERE account_name = 'Paul Salary Equity' AND account_type = 'salary_equity';
    
    -- Insert Paul's CIBC business cards if they don't exist
    INSERT INTO cibc_business_cards (
        card_name, card_type, last_four_digits, credit_limit, 
        owner_equity_account_id, default_category, is_active
    ) VALUES 
    ('CIBC Business Expenses Card', 'business_expenses', '1234', 25000.00, 
     business_account_id, 'business_general', true),
    ('CIBC Personal Allocation Card', 'personal_allocation', '5678', 15000.00, 
     personal_account_id, 'personal', true),
    ('CIBC Salary Equity Card', 'salary_equity', '9012', 10000.00, 
     salary_account_id, 'salary_equity', true)
    ON CONFLICT DO NOTHING;
END $$;

-- Create default categorization rules
INSERT INTO cibc_categorization_rules (
    rule_name, vendor_pattern, description_pattern, category, priority
) VALUES 
-- Vehicle expenses
('Gas Stations', '%shell%|%petro%|%esso%|%chevron%|%Fas Gas%', NULL, 'vehicle_expenses', 10),
('Vehicle Maintenance', '%canadian tire%|%jiffy lube%|%midas%|%repair%', NULL, 'vehicle_expenses', 10),

-- Office supplies
('Office Supplies', '%staples%|%office%|%supplies%', NULL, 'office_supplies', 20),
('Technology', '%best buy%|%future shop%|%computer%|%software%', NULL, 'office_supplies', 20),

-- Meals and entertainment
('Restaurants', '%restaurant%|%cafe%|%coffee%|%tim hortons%|%mcdonalds%', NULL, 'meals_entertainment', 30),
('Entertainment', '%entertainment%|%movie%|%theater%|%event%', NULL, 'meals_entertainment', 30),

-- Travel
('Hotels', '%hotel%|%inn%|%resort%|%motel%', NULL, 'travel', 40),
('Airlines', '%airline%|%flight%|%westjet%|%air canada%', NULL, 'travel', 40),
('Car Rental', '%rental%|%hertz%|%avis%|%budget%', NULL, 'travel', 40),

-- Utilities and services
('Phone/Internet', '%telus%|%rogers%|%bell%|%sasktel%|%phone%|%internet%', NULL, 'utilities', 50),
('Insurance', '%insurance%|%policy%|%aviva%|%sgi%', NULL, 'insurance', 50),

-- Professional services
('Legal/Accounting', '%legal%|%accounting%|%lawyer%|%accountant%|%professional%', NULL, 'professional_services', 60),
('Banking Fees', '%fee%|%charge%|%service%|%monthly%', '%bank%|%cibc%', 'banking_fees', 60),

-- Personal (lowest priority - catch remaining)
('Personal Expenses', NULL, NULL, 'personal', 100)
ON CONFLICT DO NOTHING;

-- Update triggers for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_cibc_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_cibc_cards_updated_at
    BEFORE UPDATE ON cibc_business_cards
    FOR EACH ROW EXECUTE FUNCTION update_cibc_updated_at();

CREATE TRIGGER update_cibc_transactions_updated_at
    BEFORE UPDATE ON cibc_card_transactions
    FOR EACH ROW EXECUTE FUNCTION update_cibc_updated_at();

-- CIBC Card Management Views
CREATE OR REPLACE VIEW cibc_cards_summary AS
SELECT 
    cc.card_id,
    cc.card_name,
    cc.card_type,
    cc.last_four_digits,
    cc.credit_limit,
    cc.current_balance,
    cc.credit_limit - cc.current_balance as available_credit,
    cc.is_active,
    oa.account_name as equity_account_name,
    
    -- Current month spending
    COALESCE(current_month.monthly_spending, 0) as current_month_spending,
    COALESCE(current_month.transaction_count, 0) as current_month_transactions,
    
    -- Last transaction
    latest.last_transaction_date,
    latest.last_vendor,
    latest.last_amount,
    
    -- Utilization rate
    CASE WHEN cc.credit_limit > 0 
         THEN (cc.current_balance / cc.credit_limit * 100)
         ELSE 0 END as utilization_rate
         
FROM cibc_business_cards cc
LEFT JOIN owner_equity_accounts oa ON cc.owner_equity_account_id = oa.account_id
LEFT JOIN (
    SELECT 
        card_id,
        SUM(amount) as monthly_spending,
        COUNT(*) as transaction_count
    FROM cibc_card_transactions
    WHERE DATE_TRUNC('month', transaction_date) = DATE_TRUNC('month', CURRENT_DATE)
    GROUP BY card_id
) current_month ON cc.card_id = current_month.card_id
LEFT JOIN (
    SELECT DISTINCT ON (card_id)
        card_id,
        transaction_date as last_transaction_date,
        vendor_name as last_vendor,
        amount as last_amount
    FROM cibc_card_transactions
    ORDER BY card_id, transaction_date DESC
) latest ON cc.card_id = latest.card_id
ORDER BY cc.card_type, cc.card_name;

-- Monthly spending analysis view
CREATE OR REPLACE VIEW cibc_monthly_analysis AS
SELECT 
    DATE_TRUNC('month', ct.transaction_date) as month,
    cc.card_type,
    cc.card_name,
    COUNT(*) as transaction_count,
    SUM(ct.amount) as total_spending,
    AVG(ct.amount) as avg_transaction,
    COUNT(DISTINCT ct.vendor_name) as unique_vendors,
    
    -- Category breakdown
    COUNT(CASE WHEN ct.category = 'vehicle_expenses' THEN 1 END) as vehicle_transactions,
    SUM(CASE WHEN ct.category = 'vehicle_expenses' THEN ct.amount ELSE 0 END) as vehicle_spending,
    
    COUNT(CASE WHEN ct.category = 'meals_entertainment' THEN 1 END) as meals_transactions,
    SUM(CASE WHEN ct.category = 'meals_entertainment' THEN ct.amount ELSE 0 END) as meals_spending,
    
    COUNT(CASE WHEN ct.category = 'office_supplies' THEN 1 END) as office_transactions,
    SUM(CASE WHEN ct.category = 'office_supplies' THEN ct.amount ELSE 0 END) as office_spending,
    
    COUNT(CASE WHEN ct.category = 'travel' THEN 1 END) as travel_transactions,
    SUM(CASE WHEN ct.category = 'travel' THEN ct.amount ELSE 0 END) as travel_spending,
    
    COUNT(CASE WHEN ct.category IS NULL OR ct.category = 'uncategorized' THEN 1 END) as uncategorized_transactions
    
FROM cibc_card_transactions ct
INNER JOIN cibc_business_cards cc ON ct.card_id = cc.card_id
WHERE ct.transaction_date >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY DATE_TRUNC('month', ct.transaction_date), cc.card_type, cc.card_name, cc.card_id
ORDER BY month DESC, cc.card_type;

-- Vendor analysis view
CREATE OR REPLACE VIEW cibc_vendor_analysis AS
SELECT 
    ct.vendor_name,
    COUNT(*) as transaction_count,
    SUM(ct.amount) as total_amount,
    AVG(ct.amount) as avg_amount,
    MIN(ct.transaction_date) as first_transaction,
    MAX(ct.transaction_date) as last_transaction,
    COUNT(DISTINCT ct.card_id) as cards_used,
    
    -- Most common category
    (SELECT category 
     FROM cibc_card_transactions ct2 
     WHERE ct2.vendor_name = ct.vendor_name 
       AND ct2.category IS NOT NULL
     GROUP BY category 
     ORDER BY COUNT(*) DESC 
     LIMIT 1) as most_common_category,
     
    -- Frequency (transactions per month)
    ROUND(COUNT(*) / GREATEST(DATE_PART('month', AGE(MAX(ct.transaction_date), MIN(ct.transaction_date))) + 1, 1), 2) as transactions_per_month
    
FROM cibc_card_transactions ct
WHERE ct.vendor_name IS NOT NULL 
  AND ct.transaction_date >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY ct.vendor_name
HAVING COUNT(*) >= 2  -- Only show vendors with multiple transactions
ORDER BY total_amount DESC;

-- Grant permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON cibc_business_cards TO postgres;
GRANT SELECT, INSERT, UPDATE, DELETE ON cibc_card_transactions TO postgres;
GRANT SELECT, INSERT, UPDATE, DELETE ON cibc_statement_uploads TO postgres;
GRANT SELECT, INSERT, UPDATE, DELETE ON cibc_categorization_rules TO postgres;

GRANT USAGE, SELECT ON SEQUENCE cibc_business_cards_card_id_seq TO postgres;
GRANT USAGE, SELECT ON SEQUENCE cibc_card_transactions_transaction_id_seq TO postgres;
GRANT USAGE, SELECT ON SEQUENCE cibc_statement_uploads_upload_id_seq TO postgres;
GRANT USAGE, SELECT ON SEQUENCE cibc_categorization_rules_rule_id_seq TO postgres;

GRANT SELECT ON cibc_cards_summary, cibc_monthly_analysis, cibc_vendor_analysis TO postgres;

COMMIT;

-- Summary output
DO $$
DECLARE
    card_count INTEGER;
    transaction_count INTEGER;
    rule_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO card_count FROM cibc_business_cards;
    SELECT COUNT(*) INTO transaction_count FROM cibc_card_transactions;
    SELECT COUNT(*) INTO rule_count FROM cibc_categorization_rules;
    
    RAISE NOTICE '';
    RAISE NOTICE '=== CIBC Business Card Management System Created ===';
    RAISE NOTICE 'Business Cards: %', card_count;
    RAISE NOTICE 'Transactions: %', transaction_count;
    RAISE NOTICE 'Categorization Rules: %', rule_count;
    RAISE NOTICE '';
    RAISE NOTICE 'Tables Created:';
    RAISE NOTICE '  - cibc_business_cards (Paul''s 3 cards)';
    RAISE NOTICE '  - cibc_card_transactions (transaction tracking)';
    RAISE NOTICE '  - cibc_statement_uploads (file processing)';
    RAISE NOTICE '  - cibc_categorization_rules (auto-categorization)';
    RAISE NOTICE '';
    RAISE NOTICE 'Views Created:';
    RAISE NOTICE '  - cibc_cards_summary (card overview)';
    RAISE NOTICE '  - cibc_monthly_analysis (spending patterns)';
    RAISE NOTICE '  - cibc_vendor_analysis (vendor insights)';
    RAISE NOTICE '';
    RAISE NOTICE 'Paul''s CIBC Cards:';
    RAISE NOTICE '  - Business Expenses (**** 1234) - $25,000 limit';
    RAISE NOTICE '  - Personal Allocation (**** 5678) - $15,000 limit';
    RAISE NOTICE '  - Salary Equity (**** 9012) - $10,000 limit';
    RAISE NOTICE '';
    RAISE NOTICE '✅ CIBC Card Management System ready for use';
END $$;