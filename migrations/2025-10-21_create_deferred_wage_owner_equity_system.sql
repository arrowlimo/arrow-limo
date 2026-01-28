-- ============================================================================
-- DEFERRED WAGE & OWNER EQUITY TRACKING SYSTEM
-- ============================================================================
-- Created: October 21, 2025
-- Purpose: Track deferred wages, owner expenses, equity balances, and T4 compliance
--
-- Business Requirements:
-- 1. Deferred wage allocations for cash flow management
-- 2. Owner expense tracking (Paul's CIBC business card vs personal allocation)
-- 3. Equity balances and owed amounts for all employees
-- 4. Michael Richard's extensive deferred pay tracking
-- 5. T4 compliance corrections for owner salary (2013 issue)
-- ============================================================================

-- 1. DEFERRED WAGE ACCOUNTS
-- ==========================
-- Track deferred wages for employees who receive partial pay
-- to allow better cash flow allocation across workforce
CREATE TABLE deferred_wage_accounts (
    account_id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    
    -- Account Information
    account_name VARCHAR(100),                -- "Michael Richard Deferred", "Driver Pool", etc.
    account_type VARCHAR(30) DEFAULT 'employee_deferred', -- 'employee_deferred', 'owner_equity', 'pool_allocation'
    account_status VARCHAR(20) DEFAULT 'active', -- 'active', 'suspended', 'closed'
    
    -- Current Balance Tracking
    current_balance DECIMAL(12,2) DEFAULT 0,  -- Amount currently owed to employee
    ytd_deferred_amount DECIMAL(12,2) DEFAULT 0, -- Year-to-date deferred wages
    ytd_paid_amount DECIMAL(12,2) DEFAULT 0,  -- Year-to-date actual payments
    
    -- Historical Totals
    lifetime_deferred DECIMAL(12,2) DEFAULT 0, -- Total ever deferred
    lifetime_paid DECIMAL(12,2) DEFAULT 0,     -- Total ever paid out
    
    -- Interest and Adjustment Tracking
    interest_rate DECIMAL(5,4) DEFAULT 0,     -- Annual interest rate on deferred wages
    last_interest_calculation DATE,
    accumulated_interest DECIMAL(12,2) DEFAULT 0,
    
    -- Account Settings
    max_deferred_amount DECIMAL(12,2),        -- Maximum deferred balance allowed
    minimum_payment_frequency VARCHAR(20) DEFAULT 'monthly', -- 'weekly', 'monthly', 'quarterly'
    auto_payment_enabled BOOLEAN DEFAULT FALSE,
    auto_payment_amount DECIMAL(12,2),
    
    -- Audit Fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES employees(employee_id)
);

-- 2. DEFERRED WAGE TRANSACTIONS
-- =============================
-- Detailed transaction log for all deferred wage activities
CREATE TABLE deferred_wage_transactions (
    transaction_id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES deferred_wage_accounts(account_id),
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    
    -- Transaction Details
    transaction_date DATE NOT NULL,
    transaction_type VARCHAR(30) NOT NULL,    -- 'deferral', 'payment', 'interest', 'adjustment', 'forgiveness'
    description TEXT,
    
    -- Financial Amounts
    gross_amount DECIMAL(12,2) NOT NULL,      -- Original amount (before taxes)
    deferred_amount DECIMAL(12,2),            -- Amount deferred (can be partial)
    paid_amount DECIMAL(12,2),                -- Amount actually paid
    tax_withholdings DECIMAL(12,2) DEFAULT 0, -- Taxes held on paid portion
    net_payment DECIMAL(12,2),                -- Net amount to employee
    
    -- Source References
    payroll_id INTEGER,                       -- Links to driver_payroll or automated_salary_bookings
    charter_id INTEGER REFERENCES charters(charter_id), -- If from specific charter
    expense_id INTEGER,                       -- If related to expense reimbursement
    
    -- Balance Impact
    balance_before DECIMAL(12,2),
    balance_after DECIMAL(12,2),
    
    -- Processing Information
    processed_by INTEGER REFERENCES employees(employee_id),
    processing_notes TEXT,
    approved_by INTEGER REFERENCES employees(employee_id),
    approval_date TIMESTAMP,
    
    -- Accounting Integration
    journal_entry_id INTEGER,                 -- Links to general ledger
    qb_transaction_id VARCHAR(50),            -- QuickBooks integration
    
    -- Audit Fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. OWNER EQUITY & EXPENSE TRACKING
-- ==================================
-- Track owner (Paul) business expenses vs personal allocation
CREATE TABLE owner_equity_accounts (
    equity_account_id SERIAL PRIMARY KEY,
    owner_name VARCHAR(100) NOT NULL,         -- "Paul Heffner"
    account_type VARCHAR(30) NOT NULL,        -- 'business_expenses', 'personal_allocation', 'salary_equity'
    
    -- Account Balances
    current_balance DECIMAL(12,2) DEFAULT 0,  -- Current equity balance (can be negative)
    ytd_business_expenses DECIMAL(12,2) DEFAULT 0, -- YTD business expenses
    ytd_personal_allocation DECIMAL(12,2) DEFAULT 0, -- YTD personal allocations (income)
    ytd_salary_equivalent DECIMAL(12,2) DEFAULT 0, -- YTD salary equivalent calculations
    
    -- Business Card Integration
    cibc_card_number VARCHAR(20),             -- CIBC business card number (masked)
    card_nickname VARCHAR(50),                -- "Main Business Card", "Fuel Card", etc.
    monthly_limit DECIMAL(12,2),
    
    -- T4 Compliance Tracking
    t4_reportable_income DECIMAL(12,2) DEFAULT 0, -- Annual T4 reportable amount
    t4_corrections_needed BOOLEAN DEFAULT FALSE,   -- Flag for 2013 T4 correction
    correction_notes TEXT,
    
    -- Audit Fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. OWNER EXPENSE TRANSACTIONS
-- =============================
-- Detailed tracking of owner business expenses and personal allocations
CREATE TABLE owner_expense_transactions (
    transaction_id SERIAL PRIMARY KEY,
    equity_account_id INTEGER NOT NULL REFERENCES owner_equity_accounts(equity_account_id),
    
    -- Transaction Details
    transaction_date DATE NOT NULL,
    transaction_type VARCHAR(30) NOT NULL,    -- 'business_expense', 'personal_allocation', 'salary_equivalent'
    description TEXT NOT NULL,
    
    -- Financial Details
    gross_amount DECIMAL(12,2) NOT NULL,
    business_portion DECIMAL(12,2) DEFAULT 0, -- Business deductible portion
    personal_portion DECIMAL(12,2) DEFAULT 0, -- Personal income portion
    tax_implications TEXT,                     -- Notes on tax treatment
    
    -- Source Information
    expense_category VARCHAR(50),             -- 'fuel', 'meals', 'equipment', 'personal_draw'
    vendor_name VARCHAR(200),
    receipt_reference VARCHAR(100),
    
    -- Banking Integration
    cibc_transaction_id VARCHAR(50),          -- CIBC transaction reference
    banking_transaction_id INTEGER REFERENCES banking_transactions(transaction_id),
    card_used VARCHAR(20),                    -- Which CIBC card was used
    
    -- Approval Workflow
    requires_approval BOOLEAN DEFAULT TRUE,
    approved_by VARCHAR(100),                 -- Can be external accountant
    approval_date TIMESTAMP,
    approval_notes TEXT,
    
    -- Accounting Integration
    journal_entry_id INTEGER,
    qb_account VARCHAR(100),                  -- QuickBooks account classification
    cra_category VARCHAR(50),                 -- CRA expense category for tax purposes
    
    -- Audit Fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. WAGE ALLOCATION POOL
-- =======================
-- Track pool of available funds for wage allocation decisions
CREATE TABLE wage_allocation_pool (
    pool_id SERIAL PRIMARY KEY,
    pool_name VARCHAR(100) NOT NULL,          -- "Weekly Driver Pool", "Monthly Salary Pool"
    pool_type VARCHAR(30) NOT NULL,           -- 'driver_pool', 'salary_pool', 'bonus_pool'
    
    -- Pool Funding
    total_available DECIMAL(12,2) NOT NULL,   -- Total funds available for allocation
    allocated_amount DECIMAL(12,2) DEFAULT 0, -- Amount already allocated
    remaining_balance DECIMAL(12,2) DEFAULT 0, -- Available for new allocations
    
    -- Time Period
    allocation_period_start DATE NOT NULL,
    allocation_period_end DATE NOT NULL,
    allocation_frequency VARCHAR(20),         -- 'weekly', 'bi_weekly', 'monthly'
    
    -- Business Rules
    priority_employees TEXT,                  -- JSON array of high-priority employee IDs
    minimum_allocation_per_employee DECIMAL(10,2) DEFAULT 0,
    maximum_allocation_per_employee DECIMAL(10,2),
    emergency_reserve_percentage DECIMAL(5,2) DEFAULT 10, -- % to hold in reserve
    
    -- Status Tracking
    pool_status VARCHAR(20) DEFAULT 'active', -- 'active', 'closed', 'depleted'
    allocation_complete BOOLEAN DEFAULT FALSE,
    
    -- Audit Fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES employees(employee_id)
);

-- 6. WAGE ALLOCATION DECISIONS
-- ============================
-- Track individual allocation decisions from pools to employees
CREATE TABLE wage_allocation_decisions (
    allocation_id SERIAL PRIMARY KEY,
    pool_id INTEGER NOT NULL REFERENCES wage_allocation_pool(pool_id),
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    
    -- Allocation Details
    allocation_date DATE NOT NULL,
    earned_amount DECIMAL(12,2) NOT NULL,     -- Amount employee earned
    allocated_amount DECIMAL(12,2) NOT NULL,  -- Amount allocated to employee
    deferred_amount DECIMAL(12,2) DEFAULT 0,  -- Amount deferred for cash flow
    
    -- Decision Rationale
    allocation_percentage DECIMAL(5,2),       -- % of earned amount allocated
    priority_level INTEGER DEFAULT 5,         -- 1=highest, 10=lowest priority
    decision_reason TEXT,                     -- Why this allocation amount
    
    -- Employee Situation
    employee_financial_priority VARCHAR(30),  -- 'critical', 'high', 'normal', 'low'
    has_other_income BOOLEAN DEFAULT FALSE,
    family_dependents INTEGER DEFAULT 0,
    
    -- Payment Method
    payment_method VARCHAR(30),              -- 'immediate', 'deferred', 'mixed'
    immediate_payment DECIMAL(12,2) DEFAULT 0,
    deferred_wage_account_id INTEGER REFERENCES deferred_wage_accounts(account_id),
    
    -- Approval Chain
    recommended_by INTEGER REFERENCES employees(employee_id),
    approved_by INTEGER REFERENCES employees(employee_id),
    approval_date TIMESTAMP,
    
    -- Audit Fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. T4 COMPLIANCE CORRECTIONS
-- ============================
-- Track T4 corrections needed, especially for 2013 owner salary issue
CREATE TABLE t4_compliance_corrections (
    correction_id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    
    -- Tax Year Information
    tax_year INTEGER NOT NULL,                -- 2013, 2024, etc.
    correction_type VARCHAR(30) NOT NULL,     -- 'original_filing', 'amendment', 'cancellation'
    correction_reason TEXT,
    
    -- Original T4 Information
    original_t4_issued BOOLEAN DEFAULT FALSE,
    original_employment_income DECIMAL(12,2), -- Box 14
    original_cpp_contributions DECIMAL(10,2), -- Box 16
    original_ei_contributions DECIMAL(10,2),  -- Box 18
    original_income_tax DECIMAL(10,2),        -- Box 22
    
    -- Corrected T4 Information
    corrected_employment_income DECIMAL(12,2),
    corrected_cpp_contributions DECIMAL(10,2),
    corrected_ei_contributions DECIMAL(10,2),
    corrected_income_tax DECIMAL(10,2),
    
    -- Variance Analysis
    income_variance DECIMAL(12,2),            -- Difference in reported income
    cpp_variance DECIMAL(10,2),
    ei_variance DECIMAL(10,2),
    tax_variance DECIMAL(10,2),
    
    -- Correction Status
    correction_status VARCHAR(30) DEFAULT 'pending', -- 'pending', 'filed', 'accepted', 'rejected'
    cra_reference_number VARCHAR(50),
    filed_date DATE,
    cra_response_date DATE,
    cra_notes TEXT,
    
    -- Impact on Deferred Wages
    impacts_deferred_wages BOOLEAN DEFAULT FALSE,
    deferred_wage_adjustment DECIMAL(12,2),
    
    -- Audit Fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    prepared_by INTEGER REFERENCES employees(employee_id)
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Deferred Wage Accounts
CREATE INDEX idx_deferred_wage_accounts_employee_id ON deferred_wage_accounts(employee_id);
CREATE INDEX idx_deferred_wage_accounts_status ON deferred_wage_accounts(account_status);
CREATE INDEX idx_deferred_wage_accounts_balance ON deferred_wage_accounts(current_balance);

-- Deferred Wage Transactions
CREATE INDEX idx_deferred_wage_transactions_account_id ON deferred_wage_transactions(account_id);
CREATE INDEX idx_deferred_wage_transactions_employee_id ON deferred_wage_transactions(employee_id);
CREATE INDEX idx_deferred_wage_transactions_date ON deferred_wage_transactions(transaction_date);
CREATE INDEX idx_deferred_wage_transactions_type ON deferred_wage_transactions(transaction_type);

-- Owner Equity Accounts
CREATE INDEX idx_owner_equity_accounts_type ON owner_equity_accounts(account_type);
CREATE INDEX idx_owner_equity_accounts_owner ON owner_equity_accounts(owner_name);

-- Owner Expense Transactions
CREATE INDEX idx_owner_expense_transactions_equity_id ON owner_expense_transactions(equity_account_id);
CREATE INDEX idx_owner_expense_transactions_date ON owner_expense_transactions(transaction_date);
CREATE INDEX idx_owner_expense_transactions_type ON owner_expense_transactions(transaction_type);
CREATE INDEX idx_owner_expense_transactions_approval ON owner_expense_transactions(approved_by, approval_date);

-- Wage Allocation Pool
CREATE INDEX idx_wage_allocation_pool_period ON wage_allocation_pool(allocation_period_start, allocation_period_end);
CREATE INDEX idx_wage_allocation_pool_status ON wage_allocation_pool(pool_status);

-- Wage Allocation Decisions
CREATE INDEX idx_wage_allocation_decisions_pool_id ON wage_allocation_decisions(pool_id);
CREATE INDEX idx_wage_allocation_decisions_employee_id ON wage_allocation_decisions(employee_id);
CREATE INDEX idx_wage_allocation_decisions_date ON wage_allocation_decisions(allocation_date);

-- T4 Compliance Corrections
CREATE INDEX idx_t4_compliance_corrections_employee_id ON t4_compliance_corrections(employee_id);
CREATE INDEX idx_t4_compliance_corrections_tax_year ON t4_compliance_corrections(tax_year);
CREATE INDEX idx_t4_compliance_corrections_status ON t4_compliance_corrections(correction_status);

-- ============================================================================
-- TRIGGERS FOR AUTOMATIC BALANCE UPDATES
-- ============================================================================

-- Update deferred wage account balances after transaction
CREATE OR REPLACE FUNCTION update_deferred_wage_balance()
RETURNS TRIGGER AS $$
BEGIN
    -- Update the account balance based on transaction type
    IF NEW.transaction_type IN ('deferral', 'interest') THEN
        UPDATE deferred_wage_accounts 
        SET current_balance = current_balance + NEW.deferred_amount,
            updated_at = CURRENT_TIMESTAMP
        WHERE account_id = NEW.account_id;
    ELSIF NEW.transaction_type = 'payment' THEN
        UPDATE deferred_wage_accounts 
        SET current_balance = current_balance - NEW.paid_amount,
            updated_at = CURRENT_TIMESTAMP
        WHERE account_id = NEW.account_id;
    ELSIF NEW.transaction_type = 'adjustment' THEN
        UPDATE deferred_wage_accounts 
        SET current_balance = current_balance + (NEW.deferred_amount - COALESCE(NEW.paid_amount, 0)),
            updated_at = CURRENT_TIMESTAMP
        WHERE account_id = NEW.account_id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_deferred_wage_balance
    AFTER INSERT ON deferred_wage_transactions
    FOR EACH ROW
    EXECUTE FUNCTION update_deferred_wage_balance();

-- Update wage allocation pool remaining balance
CREATE OR REPLACE FUNCTION update_allocation_pool_balance()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE wage_allocation_pool 
    SET allocated_amount = (
        SELECT COALESCE(SUM(allocated_amount), 0) 
        FROM wage_allocation_decisions 
        WHERE pool_id = NEW.pool_id
    ),
    remaining_balance = total_available - (
        SELECT COALESCE(SUM(allocated_amount), 0) 
        FROM wage_allocation_decisions 
        WHERE pool_id = NEW.pool_id
    ),
    updated_at = CURRENT_TIMESTAMP
    WHERE pool_id = NEW.pool_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_allocation_pool_balance
    AFTER INSERT OR UPDATE OR DELETE ON wage_allocation_decisions
    FOR EACH ROW
    EXECUTE FUNCTION update_allocation_pool_balance();

-- ============================================================================
-- INITIAL DATA SETUP
-- ============================================================================

-- Create Paul Heffner's owner equity accounts
INSERT INTO owner_equity_accounts (owner_name, account_type, cibc_card_number, card_nickname) VALUES
('Paul Heffner', 'business_expenses', '**** **** **** 1234', 'Main CIBC Business Card'),
('Paul Heffner', 'personal_allocation', NULL, 'Personal Income Allocation'),
('Paul Heffner', 'salary_equity', NULL, 'Salary Equivalent Tracking');

-- Create Michael Richard's deferred wage account (if he exists in employees table)
INSERT INTO deferred_wage_accounts (employee_id, account_name, account_type, max_deferred_amount)
SELECT employee_id, 'Michael Richard Deferred Wages', 'employee_deferred', 50000.00
FROM employees 
WHERE LOWER(full_name) LIKE '%michael%richard%' 
   OR LOWER(full_name) LIKE '%richard%michael%'
LIMIT 1;

-- Create default wage allocation pools
INSERT INTO wage_allocation_pool (pool_name, pool_type, total_available, allocation_period_start, allocation_period_end, allocation_frequency)
VALUES 
('Weekly Driver Pool', 'driver_pool', 0, CURRENT_DATE - INTERVAL '7 days', CURRENT_DATE, 'weekly'),
('Monthly Salary Pool', 'salary_pool', 0, DATE_TRUNC('month', CURRENT_DATE), DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month' - INTERVAL '1 day', 'monthly');

-- Flag 2013 T4 correction needed for Paul Heffner (if he exists in employees)
INSERT INTO t4_compliance_corrections (employee_id, tax_year, correction_type, correction_reason, correction_status)
SELECT employee_id, 2013, 'amendment', 'Owner received T4 in 2013 but should not have - technically on salary equity system', 'pending'
FROM employees 
WHERE LOWER(full_name) LIKE '%paul%heffner%' 
   OR LOWER(full_name) LIKE '%heffner%paul%'
LIMIT 1;

-- ============================================================================
-- VIEWS FOR REPORTING
-- ============================================================================

-- Comprehensive deferred wage summary by employee
CREATE VIEW v_deferred_wage_summary AS
SELECT 
    e.employee_id,
    e.full_name,
    dwa.account_id,
    dwa.account_name,
    dwa.current_balance,
    dwa.ytd_deferred_amount,
    dwa.ytd_paid_amount,
    dwa.lifetime_deferred,
    dwa.lifetime_paid,
    dwa.accumulated_interest,
    dwa.account_status,
    dwa.last_interest_calculation,
    COUNT(dwt.transaction_id) as total_transactions,
    MAX(dwt.transaction_date) as last_transaction_date
FROM employees e
JOIN deferred_wage_accounts dwa ON e.employee_id = dwa.employee_id
LEFT JOIN deferred_wage_transactions dwt ON dwa.account_id = dwt.account_id
GROUP BY e.employee_id, e.full_name, dwa.account_id, dwa.account_name, 
         dwa.current_balance, dwa.ytd_deferred_amount, dwa.ytd_paid_amount,
         dwa.lifetime_deferred, dwa.lifetime_paid, dwa.accumulated_interest,
         dwa.account_status, dwa.last_interest_calculation;

-- Owner expense summary with business vs personal breakdown
CREATE VIEW v_owner_expense_summary AS
SELECT 
    oea.owner_name,
    oea.account_type,
    oea.current_balance,
    oea.ytd_business_expenses,
    oea.ytd_personal_allocation,
    oea.t4_reportable_income,
    COUNT(oet.transaction_id) as total_transactions,
    SUM(CASE WHEN oet.transaction_type = 'business_expense' THEN oet.business_portion ELSE 0 END) as total_business_expenses,
    SUM(CASE WHEN oet.transaction_type = 'personal_allocation' THEN oet.personal_portion ELSE 0 END) as total_personal_allocations,
    MAX(oet.transaction_date) as last_transaction_date
FROM owner_equity_accounts oea
LEFT JOIN owner_expense_transactions oet ON oea.equity_account_id = oet.equity_account_id
GROUP BY oea.owner_name, oea.account_type, oea.current_balance, 
         oea.ytd_business_expenses, oea.ytd_personal_allocation, oea.t4_reportable_income;

-- Current wage allocation pool status
CREATE VIEW v_wage_allocation_pool_status AS
SELECT 
    wap.pool_id,
    wap.pool_name,
    wap.pool_type,
    wap.total_available,
    wap.allocated_amount,
    wap.remaining_balance,
    wap.allocation_period_start,
    wap.allocation_period_end,
    wap.pool_status,
    COUNT(wad.allocation_id) as total_allocations,
    COUNT(DISTINCT wad.employee_id) as employees_allocated
FROM wage_allocation_pool wap
LEFT JOIN wage_allocation_decisions wad ON wap.pool_id = wad.pool_id
GROUP BY wap.pool_id, wap.pool_name, wap.pool_type, wap.total_available,
         wap.allocated_amount, wap.remaining_balance, wap.allocation_period_start,
         wap.allocation_period_end, wap.pool_status;

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE deferred_wage_accounts IS 'Employee deferred wage accounts for cash flow management';
COMMENT ON TABLE deferred_wage_transactions IS 'Detailed log of all deferred wage activities';
COMMENT ON TABLE owner_equity_accounts IS 'Owner (Paul) business expense vs personal allocation tracking';
COMMENT ON TABLE owner_expense_transactions IS 'Detailed owner expense transactions with CIBC card integration';
COMMENT ON TABLE wage_allocation_pool IS 'Available funds pool for strategic wage allocation decisions';
COMMENT ON TABLE wage_allocation_decisions IS 'Individual allocation decisions from pools to employees';
COMMENT ON TABLE t4_compliance_corrections IS 'T4 corrections tracking including 2013 owner salary issue';

COMMENT ON COLUMN deferred_wage_accounts.current_balance IS 'Current amount owed to employee (can grow with interest)';
COMMENT ON COLUMN owner_expense_transactions.business_portion IS 'Business deductible portion of expense';
COMMENT ON COLUMN owner_expense_transactions.personal_portion IS 'Personal income portion (counted as owner income)';
COMMENT ON COLUMN wage_allocation_decisions.allocation_percentage IS 'Percentage of earned amount actually allocated';
COMMENT ON COLUMN t4_compliance_corrections.correction_reason IS 'Reason for T4 correction (e.g., 2013 owner salary issue)';