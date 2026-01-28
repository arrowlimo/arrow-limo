-- =====================================================================
-- Phase 2: QuickBooks Column Extensions
-- Date: October 16, 2025
-- Purpose: Add QB-specific columns to existing tables
-- =====================================================================

-- =================================================================
-- STEP 1: Extend chart_of_accounts with QuickBooks fields
-- =================================================================

\echo ''
\echo '====================================================================='
\echo 'STEP 1: Extending chart_of_accounts with QB fields'
\echo '====================================================================='

-- Add QB-specific columns
ALTER TABLE chart_of_accounts 
ADD COLUMN IF NOT EXISTS qb_account_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS qb_special_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS qb_tax_line_id INTEGER,
ADD COLUMN IF NOT EXISTS is_sub_account BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS full_name TEXT,
ADD COLUMN IF NOT EXISTS qb_description TEXT,
ADD COLUMN IF NOT EXISTS opening_balance DECIMAL(15,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS opening_balance_date DATE,
ADD COLUMN IF NOT EXISTS is_active_for_import BOOLEAN DEFAULT true;

-- Populate full_name with hierarchy (account_number · account_name)
UPDATE chart_of_accounts 
SET full_name = account_number || ' · ' || account_name
WHERE full_name IS NULL AND account_number IS NOT NULL;

-- Mark sub-accounts (accounts with parent_account_id)
UPDATE chart_of_accounts 
SET is_sub_account = true
WHERE parent_account_id IS NOT NULL;

-- Map existing account_type to qb_account_type
UPDATE chart_of_accounts 
SET qb_account_type = account_type
WHERE qb_account_type IS NULL AND account_type IS NOT NULL;

COMMENT ON COLUMN chart_of_accounts.qb_account_type IS 'QuickBooks account type enum (Bank, AccountsReceivable, OtherCurrentAsset, FixedAsset, AccountsPayable, CreditCard, OtherCurrentLiability, LongTermLiability, Equity, Income, CostOfGoodsSold, Expense, OtherIncome, OtherExpense)';
COMMENT ON COLUMN chart_of_accounts.qb_special_type IS 'Special QuickBooks account designation (ARAccount, APAccount, UndepositedFunds, etc.)';
COMMENT ON COLUMN chart_of_accounts.full_name IS 'Full hierarchical name (e.g., "1000 · CIBC Bank 1615" or "2501 · Leases and Loans:L1 - Mercedes")';

SELECT 'chart_of_accounts extended' AS status, COUNT(*) AS total_accounts FROM chart_of_accounts;

-- =================================================================
-- STEP 2: Extend journal_lines for transaction linking
-- =================================================================

\echo ''
\echo '====================================================================='
\echo 'STEP 2: Extending journal_lines for transaction linking'
\echo '====================================================================='

ALTER TABLE journal_lines
ADD COLUMN IF NOT EXISTS trans_num VARCHAR(50),
ADD COLUMN IF NOT EXISTS qb_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS split_id INTEGER,
ADD COLUMN IF NOT EXISTS is_cleared BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS reconcile_date DATE,
ADD COLUMN IF NOT EXISTS entity_type VARCHAR(20),
ADD COLUMN IF NOT EXISTS entity_id INTEGER;

-- Map existing batch_id to trans_num if not already populated
UPDATE journal_lines 
SET trans_num = batch_id::text
WHERE trans_num IS NULL AND batch_id IS NOT NULL;

-- Map existing transaction_type to qb_type
UPDATE journal_lines 
SET qb_type = transaction_type
WHERE qb_type IS NULL AND transaction_type IS NOT NULL;

-- Determine entity_type from transaction data
UPDATE journal_lines 
SET entity_type = CASE 
    WHEN merchant ILIKE '%charter%' THEN 'charter'
    WHEN merchant IS NOT NULL THEN 'vendor'
    ELSE NULL
END
WHERE entity_type IS NULL;

COMMENT ON COLUMN journal_lines.trans_num IS 'Transaction number linking to journal entry';
COMMENT ON COLUMN journal_lines.qb_type IS 'QuickBooks transaction type (Bill, Check, Invoice, Payment, Deposit, GeneralJournal, etc.)';
COMMENT ON COLUMN journal_lines.entity_type IS 'Type of entity: customer, vendor, employee, charter';
COMMENT ON COLUMN journal_lines.entity_id IS 'Foreign key to entity (client_id, vendor_id, employee_id, charter_id)';

SELECT 'journal_lines extended' AS status, COUNT(*) AS total_lines FROM journal_lines;

-- =================================================================
-- STEP 3: Extend payments with QB payment types
-- =================================================================

\echo ''
\echo '====================================================================='
\echo 'STEP 3: Extending payments with QB payment types'
\echo '====================================================================='

ALTER TABLE payments
ADD COLUMN IF NOT EXISTS qb_payment_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS applied_to_invoice INTEGER REFERENCES invoices(id),
ADD COLUMN IF NOT EXISTS qb_trans_num VARCHAR(50),
ADD COLUMN IF NOT EXISTS payment_account VARCHAR(50),
ADD COLUMN IF NOT EXISTS check_number VARCHAR(50),
ADD COLUMN IF NOT EXISTS reference_number VARCHAR(50),
ADD COLUMN IF NOT EXISTS is_deposited BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS deposit_to_account VARCHAR(50);

-- Default qb_payment_type based on payment_method
UPDATE payments 
SET qb_payment_type = CASE 
    WHEN payment_method = 'Credit Card' THEN 'CreditCard'
    WHEN payment_method = 'Cash' THEN 'Cash'
    WHEN payment_method = 'Cheque' THEN 'Check'
    WHEN payment_method = 'E-Transfer' THEN 'EFT'
    WHEN payment_method LIKE '%Square%' THEN 'CreditCard'
    ELSE 'Other'
END
WHERE qb_payment_type IS NULL;

-- Set default payment account for credit cards
UPDATE payments 
SET payment_account = '1099' -- Undeposited Funds
WHERE payment_account IS NULL AND qb_payment_type = 'CreditCard';

COMMENT ON COLUMN payments.qb_payment_type IS 'QuickBooks payment type (Cash, Check, CreditCard, EFT, etc.)';
COMMENT ON COLUMN payments.applied_to_invoice IS 'Foreign key to invoices table - which invoice this payment applies to';
COMMENT ON COLUMN payments.payment_account IS 'Account code where payment was received/deposited';

SELECT 'payments extended' AS status, COUNT(*) AS total_payments FROM payments;

-- =================================================================
-- STEP 4: Extend clients with QB customer fields
-- =================================================================

\echo ''
\echo '====================================================================='
\echo 'STEP 4: Extending clients with QB customer fields'
\echo '====================================================================='

ALTER TABLE clients
ADD COLUMN IF NOT EXISTS qb_customer_id VARCHAR(50),
ADD COLUMN IF NOT EXISTS qb_customer_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS credit_limit DECIMAL(15,2),
ADD COLUMN IF NOT EXISTS payment_terms VARCHAR(50) DEFAULT 'Net 30',
ADD COLUMN IF NOT EXISTS tax_code VARCHAR(20),
ADD COLUMN IF NOT EXISTS billing_rate_level VARCHAR(50),
ADD COLUMN IF NOT EXISTS preferred_payment_method VARCHAR(50),
ADD COLUMN IF NOT EXISTS sales_tax_code VARCHAR(20),
ADD COLUMN IF NOT EXISTS resale_number VARCHAR(50),
ADD COLUMN IF NOT EXISTS is_taxable BOOLEAN DEFAULT true;

-- Set default customer type
UPDATE clients 
SET qb_customer_type = 'Commercial'
WHERE qb_customer_type IS NULL;

-- Copy discount/gratuity percentages are already there (charter-specific)
-- Tax code for Canadian GST/HST
UPDATE clients 
SET tax_code = 'GST',
    sales_tax_code = 'GST'
WHERE tax_code IS NULL AND country = 'Canada';

COMMENT ON COLUMN clients.qb_customer_id IS 'External QuickBooks customer ID for sync';
COMMENT ON COLUMN clients.qb_customer_type IS 'Customer classification (Commercial, Residential, Wholesale, etc.)';
COMMENT ON COLUMN clients.payment_terms IS 'Payment terms (Net 30, Net 15, Due on Receipt, etc.)';

SELECT 'clients extended' AS status, COUNT(*) AS total_clients FROM clients;

-- =================================================================
-- STEP 5: Extend vendors with QB vendor fields
-- =================================================================

\echo ''
\echo '====================================================================='
\echo 'STEP 5: Extending vendors with QB vendor fields'
\echo '====================================================================='

ALTER TABLE vendors
ADD COLUMN IF NOT EXISTS qb_vendor_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS payment_terms VARCHAR(50) DEFAULT 'Net 30',
ADD COLUMN IF NOT EXISTS credit_limit DECIMAL(15,2),
ADD COLUMN IF NOT EXISTS tax_id VARCHAR(50),
ADD COLUMN IF NOT EXISTS vendor_account_number VARCHAR(50),
ADD COLUMN IF NOT EXISTS billing_rate_level VARCHAR(50),
ADD COLUMN IF NOT EXISTS is_1099_contractor BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS default_expense_account VARCHAR(50),
ADD COLUMN IF NOT EXISTS is_sales_tax_vendor BOOLEAN DEFAULT false;

-- Set vendor types based on common patterns
UPDATE vendors 
SET qb_vendor_type = CASE 
    WHEN vendor_name ILIKE '%insurance%' THEN 'Insurance'
    WHEN vendor_name ILIKE '%fuel%' OR vendor_name ILIKE '%gas%' OR vendor_name ILIKE '%petro%' THEN 'Fuel'
    WHEN vendor_name ILIKE '%repair%' OR vendor_name ILIKE '%service%' THEN 'Service'
    WHEN vendor_name ILIKE '%bank%' THEN 'Financial'
    WHEN vendor_name ILIKE '%government%' OR vendor_name ILIKE '%cra%' THEN 'Government'
    ELSE 'Supplier'
END
WHERE qb_vendor_type IS NULL;

-- quickbooks_id already exists - map to qb_vendor_id for consistency
-- (column already exists based on previous analysis)

COMMENT ON COLUMN vendors.qb_vendor_type IS 'Vendor classification (Supplier, Service, Fuel, Insurance, Financial, Government, etc.)';
COMMENT ON COLUMN vendors.payment_terms IS 'Payment terms with this vendor (Net 30, Net 15, Due on Receipt, etc.)';
COMMENT ON COLUMN vendors.is_1099_contractor IS 'US tax form 1099 contractor status';

SELECT 'vendors extended' AS status, COUNT(*) AS total_vendors FROM vendors;

-- =================================================================
-- STEP 6: Extend payables with QB invoice tracking
-- =================================================================

\echo ''
\echo '====================================================================='
\echo 'STEP 6: Extending payables with QB invoice tracking'
\echo '====================================================================='

ALTER TABLE payables
ADD COLUMN IF NOT EXISTS qb_txn_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS qb_trans_num VARCHAR(50),
ADD COLUMN IF NOT EXISTS payment_status VARCHAR(20) DEFAULT 'Open',
ADD COLUMN IF NOT EXISTS paid_amount DECIMAL(15,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS remaining_balance DECIMAL(15,2),
ADD COLUMN IF NOT EXISTS discount_amount DECIMAL(15,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS payment_date DATE,
ADD COLUMN IF NOT EXISTS aging_days INTEGER;

-- Set qb_txn_type based on existing data patterns
UPDATE payables 
SET qb_txn_type = 'Bill'
WHERE qb_txn_type IS NULL;

-- Calculate remaining balance (amount - paid_amount)
UPDATE payables 
SET remaining_balance = COALESCE(amount, 0) - COALESCE(paid_amount, 0)
WHERE remaining_balance IS NULL;

-- Update payment_status based on remaining balance
UPDATE payables 
SET payment_status = CASE 
    WHEN remaining_balance <= 0 THEN 'Paid'
    WHEN paid_amount > 0 AND remaining_balance > 0 THEN 'PartiallyPaid'
    ELSE 'Open'
END;

-- Calculate aging (days past due_date)
UPDATE payables 
SET aging_days = EXTRACT(DAY FROM (CURRENT_DATE - due_date))
WHERE due_date IS NOT NULL AND aging_days IS NULL;

COMMENT ON COLUMN payables.qb_txn_type IS 'QuickBooks transaction type (Bill, VendorCredit, ItemReceipt, etc.)';
COMMENT ON COLUMN payables.payment_status IS 'Payment status (Open, Paid, PartiallyPaid, Overdue)';
COMMENT ON COLUMN payables.aging_days IS 'Days overdue (negative = not due yet, positive = days past due)';

SELECT 'payables extended' AS status, COUNT(*) AS total_payables FROM payables;

-- =================================================================
-- VERIFICATION QUERIES
-- =================================================================

\echo ''
\echo '====================================================================='
\echo 'VERIFICATION: Column counts per table'
\echo '====================================================================='

SELECT 
    'chart_of_accounts' AS table_name,
    COUNT(*) AS column_count
FROM information_schema.columns 
WHERE table_name = 'chart_of_accounts'

UNION ALL

SELECT 
    'journal_lines',
    COUNT(*)
FROM information_schema.columns 
WHERE table_name = 'journal_lines'

UNION ALL

SELECT 
    'payments',
    COUNT(*)
FROM information_schema.columns 
WHERE table_name = 'payments'

UNION ALL

SELECT 
    'clients',
    COUNT(*)
FROM information_schema.columns 
WHERE table_name = 'clients'

UNION ALL

SELECT 
    'vendors',
    COUNT(*)
FROM information_schema.columns 
WHERE table_name = 'vendors'

UNION ALL

SELECT 
    'payables',
    COUNT(*)
FROM information_schema.columns 
WHERE table_name = 'payables';

\echo ''
\echo '====================================================================='
\echo '✓ Phase 2a: Column Extensions Complete!'
\echo '====================================================================='
\echo 'All tables extended with QuickBooks fields.'
\echo 'Next: Create invoices table (Phase 2b)'
\echo '====================================================================='
