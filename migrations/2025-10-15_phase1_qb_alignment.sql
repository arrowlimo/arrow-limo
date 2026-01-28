-- =====================================================================
-- Phase 1: QB Alignment Quick Wins
-- Date: October 15, 2025
-- Purpose: Rename staging table to primary journal and add indexes
-- =====================================================================

-- =================================================================
-- STEP 1: Rename qb_transactions_staging to qb_journal_entries
-- =================================================================
-- This table already has 53,779 rows with perfect QB structure
-- Including: transaction_date, account_code, account_name, debit_amount, 
--           credit_amount, transaction_type, memo, vendor_name, etc.

ALTER TABLE qb_transactions_staging 
RENAME TO qb_journal_entries;

COMMENT ON TABLE qb_journal_entries IS 
'Primary QuickBooks journal entries - all transactions from QB imports and ALMS operations. 
Formerly qb_transactions_staging. Contains 53K+ transactions with full QB compatibility.';

-- =================================================================
-- STEP 2: Add indexes to qb_journal_entries for performance
-- =================================================================

-- Index for date range queries (most common QB report filter)
CREATE INDEX IF NOT EXISTS idx_qb_journal_entries_date 
ON qb_journal_entries(transaction_date);

-- Index for account-based queries (GL reports, account activity)
CREATE INDEX IF NOT EXISTS idx_qb_journal_entries_account 
ON qb_journal_entries(account_code, transaction_date);

-- Index for transaction type filtering (Bills, Invoices, Payments, etc.)
CREATE INDEX IF NOT EXISTS idx_qb_journal_entries_type 
ON qb_journal_entries(transaction_type, transaction_date);

-- Index for vendor lookups (AP reports)
CREATE INDEX IF NOT EXISTS idx_qb_journal_entries_vendor 
ON qb_journal_entries(vendor_name, transaction_date) 
WHERE vendor_name IS NOT NULL;

-- Index for customer lookups (AR reports)
CREATE INDEX IF NOT EXISTS idx_qb_journal_entries_customer 
ON qb_journal_entries(customer_name, transaction_date) 
WHERE customer_name IS NOT NULL;

-- Composite index for amount-based searches (reconciliation, comparisons)
CREATE INDEX IF NOT EXISTS idx_qb_journal_entries_amount 
ON qb_journal_entries(transaction_date, amount);

-- Index for source hash dedupe checks
CREATE INDEX IF NOT EXISTS idx_qb_journal_entries_source_hash 
ON qb_journal_entries(source_hash) 
WHERE source_hash IS NOT NULL;

-- =================================================================
-- STEP 3: Add indexes to general_ledger for performance
-- =================================================================
-- This table has 124,324 rows with perfect QB column names

-- Index for date range queries
CREATE INDEX IF NOT EXISTS idx_general_ledger_date 
ON general_ledger(date);

-- Index for account-based queries (most important for GL reports)
CREATE INDEX IF NOT EXISTS idx_general_ledger_account 
ON general_ledger(account, date);

-- Index for transaction type filtering
CREATE INDEX IF NOT EXISTS idx_general_ledger_type 
ON general_ledger(transaction_type, date);

-- Index for name-based searches (vendor/customer activity)
CREATE INDEX IF NOT EXISTS idx_general_ledger_name 
ON general_ledger(name, date);

-- Composite index for balance queries
CREATE INDEX IF NOT EXISTS idx_general_ledger_account_balance 
ON general_ledger(account, date, balance);

-- =================================================================
-- STEP 4: Create clean view for journal table
-- =================================================================
-- The journal table has column names with spaces like "Date", "Transaction Type"
-- Create a view with proper identifiers

CREATE OR REPLACE VIEW journal_clean AS
SELECT 
    "Date" AS transaction_date,
    "Transaction Type" AS transaction_type,
    "#" AS trans_num,
    "Name" AS name,
    "Memo" AS memo,
    "Account" AS account,
    "Debit" AS debit,
    "Credit" AS credit,
    "Amount" AS amount,
    "Balance" AS balance,
    COALESCE("Debit", 0) - COALESCE("Credit", 0) AS norm_amount
FROM journal;

COMMENT ON VIEW journal_clean IS 
'Clean view of journal table with proper column identifiers (no spaces). 
Maps original columns: "Date" → transaction_date, "Transaction Type" → transaction_type, etc.
Adds norm_amount calculated field for consistent debit/credit normalization.';

-- =================================================================
-- STEP 5: Create summary views for QB-style reporting
-- =================================================================

-- View: Active accounts from COA
CREATE OR REPLACE VIEW qb_active_accounts AS
SELECT 
    account_number,
    account_name,
    account_type,
    account_level,
    parent_account_id,
    account_number || ' · ' || account_name AS full_name,
    -- Categorize by number range
    CASE 
        WHEN account_number BETWEEN 1000 AND 1999 THEN 'Assets'
        WHEN account_number BETWEEN 2000 AND 2999 THEN 'Liabilities'
        WHEN account_number BETWEEN 3000 AND 3999 THEN 'Equity'
        WHEN account_number BETWEEN 4000 AND 4999 THEN 'Income'
        WHEN account_number BETWEEN 5000 AND 5999 THEN 'Cost of Goods Sold'
        WHEN account_number BETWEEN 6000 AND 6999 THEN 'Expenses'
        WHEN account_number BETWEEN 7000 AND 7999 THEN 'Other Income'
        WHEN account_number BETWEEN 8000 AND 8999 THEN 'Other Expenses'
        ELSE 'Special'
    END AS account_category
FROM chart_of_accounts
WHERE is_active = true 
  AND account_number IS NOT NULL
ORDER BY account_number;

COMMENT ON VIEW qb_active_accounts IS 
'Active accounts from chart of accounts with QB-style full_name format (#### · Name) 
and automatic category classification based on account number ranges.';

-- View: Journal entries with account details
CREATE OR REPLACE VIEW qb_journal_with_accounts AS
SELECT 
    j.id,
    j.transaction_date,
    j.transaction_type,
    j.account_code,
    j.account_name,
    a.account_type,
    a.account_category,
    j.debit_amount,
    j.credit_amount,
    j.amount,
    j.memo,
    j.reference,
    j.vendor_name,
    j.customer_name,
    j.employee_name,
    j.check_number,
    j.invoice_number,
    j.year_extracted,
    j.created_at
FROM qb_journal_entries j
LEFT JOIN qb_active_accounts a ON j.account_code = a.account_number::text;

COMMENT ON VIEW qb_journal_with_accounts IS 
'Journal entries enriched with account type and category from chart of accounts. 
Use this view for QB-style reports that need account classification.';

-- =================================================================
-- VERIFICATION QUERIES
-- =================================================================

-- Count records in renamed table
SELECT 'qb_journal_entries record count' AS check_name, 
       COUNT(*) AS record_count 
FROM qb_journal_entries;

-- Verify indexes were created
SELECT 'qb_journal_entries indexes' AS check_name,
       COUNT(*) AS index_count
FROM pg_indexes 
WHERE tablename = 'qb_journal_entries';

-- Verify general_ledger indexes
SELECT 'general_ledger indexes' AS check_name,
       COUNT(*) AS index_count
FROM pg_indexes 
WHERE tablename = 'general_ledger';

-- Test journal_clean view
SELECT 'journal_clean view test' AS check_name,
       COUNT(*) AS record_count
FROM journal_clean;

-- Test qb_active_accounts view
SELECT 'qb_active_accounts view test' AS check_name,
       COUNT(*) AS active_accounts
FROM qb_active_accounts;

-- Show account category breakdown
SELECT account_category, COUNT(*) AS account_count
FROM qb_active_accounts
GROUP BY account_category
ORDER BY account_category;

-- =================================================================
-- COMPLETION MESSAGE
-- =================================================================
SELECT '✓ Phase 1 QB Alignment Complete!' AS status,
       'qb_journal_entries table ready with 53,779 transactions' AS detail;
