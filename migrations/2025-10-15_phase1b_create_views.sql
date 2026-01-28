-- =====================================================================
-- Phase 1b: Fix and Create Views for QB Reporting
-- Date: October 15, 2025
-- Purpose: Fix column name issues and create reporting views
-- =====================================================================

-- =================================================================
-- STEP 1: Create clean view for journal table
-- =================================================================
-- Fix: Column is "Memo/Description" not "Memo"

DROP VIEW IF EXISTS journal_clean CASCADE;

CREATE VIEW journal_clean AS
SELECT 
    "Date" AS transaction_date,
    "Transaction Type" AS transaction_type,
    "#" AS trans_num,
    "Name" AS name,
    "Memo/Description" AS memo,
    "Account" AS account,
    "Debit" AS debit,
    "Credit" AS credit,
    merchant,
    transaction_type AS transaction_type_alt,
    reference_number,
    "Reference" AS reference,
    journal_id,
    COALESCE("Debit", 0) - COALESCE("Credit", 0) AS norm_amount
FROM journal;

COMMENT ON VIEW journal_clean IS 
'Clean view of journal table with proper column identifiers (no spaces). 
Maps original columns: "Date" → transaction_date, "Memo/Description" → memo, etc.
Adds norm_amount calculated field for consistent debit/credit normalization.';

-- =================================================================
-- STEP 2: Create active accounts view
-- =================================================================
-- Fix: account_number is TEXT, need to CAST to INTEGER for comparison

DROP VIEW IF EXISTS qb_active_accounts CASCADE;

CREATE VIEW qb_active_accounts AS
SELECT 
    account_number,
    account_name,
    account_type,
    account_level,
    parent_account_id,
    account_number || ' · ' || account_name AS full_name,
    -- Categorize by number range (cast to int for comparison)
    CASE 
        WHEN account_number ~ '^\d+$' THEN
            CASE 
                WHEN account_number::integer BETWEEN 1000 AND 1999 THEN 'Assets'
                WHEN account_number::integer BETWEEN 2000 AND 2999 THEN 'Liabilities'
                WHEN account_number::integer BETWEEN 3000 AND 3999 THEN 'Equity'
                WHEN account_number::integer BETWEEN 4000 AND 4999 THEN 'Income'
                WHEN account_number::integer BETWEEN 5000 AND 5999 THEN 'Cost of Goods Sold'
                WHEN account_number::integer BETWEEN 6000 AND 6999 THEN 'Expenses'
                WHEN account_number::integer BETWEEN 7000 AND 7999 THEN 'Other Income'
                WHEN account_number::integer BETWEEN 8000 AND 8999 THEN 'Other Expenses'
                ELSE 'Special'
            END
        ELSE 'Special'
    END AS account_category
FROM chart_of_accounts
WHERE is_active = true 
  AND account_number IS NOT NULL
ORDER BY account_number;

COMMENT ON VIEW qb_active_accounts IS 
'Active accounts from chart of accounts with QB-style full_name format (#### · Name) 
and automatic category classification based on account number ranges.
Handles TEXT account_number field with regex and casting.';

-- =================================================================
-- STEP 3: Create journal entries with account details view
-- =================================================================

DROP VIEW IF EXISTS qb_journal_with_accounts CASCADE;

CREATE VIEW qb_journal_with_accounts AS
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
LEFT JOIN qb_active_accounts a ON j.account_code = a.account_number;

COMMENT ON VIEW qb_journal_with_accounts IS 
'Journal entries enriched with account type and category from chart of accounts. 
Use this view for QB-style reports that need account classification.';

-- =================================================================
-- STEP 4: Create useful summary views for QB reporting
-- =================================================================

-- View: Transaction type summary
DROP VIEW IF EXISTS qb_transaction_type_summary CASCADE;

CREATE VIEW qb_transaction_type_summary AS
SELECT 
    transaction_type,
    COUNT(*) AS transaction_count,
    SUM(debit_amount) AS total_debits,
    SUM(credit_amount) AS total_credits,
    MIN(transaction_date) AS first_date,
    MAX(transaction_date) AS last_date
FROM qb_journal_entries
WHERE transaction_type IS NOT NULL
GROUP BY transaction_type
ORDER BY transaction_count DESC;

COMMENT ON VIEW qb_transaction_type_summary IS 
'Summary of all transaction types in QB journal with counts and totals.';

-- View: Account activity summary
DROP VIEW IF EXISTS qb_account_activity_summary CASCADE;

CREATE VIEW qb_account_activity_summary AS
SELECT 
    a.account_number,
    a.account_name,
    a.account_type,
    a.account_category,
    COUNT(j.id) AS transaction_count,
    SUM(j.debit_amount) AS total_debits,
    SUM(j.credit_amount) AS total_credits,
    SUM(COALESCE(j.debit_amount, 0) - COALESCE(j.credit_amount, 0)) AS net_amount
FROM qb_active_accounts a
LEFT JOIN qb_journal_entries j ON a.account_number = j.account_code
GROUP BY a.account_number, a.account_name, a.account_type, a.account_category
ORDER BY a.account_number;

COMMENT ON VIEW qb_account_activity_summary IS 
'Activity summary for each account showing transaction counts and totals.';

-- View: Monthly transaction summary
DROP VIEW IF EXISTS qb_monthly_summary CASCADE;

CREATE VIEW qb_monthly_summary AS
SELECT 
    DATE_TRUNC('month', transaction_date) AS month,
    COUNT(*) AS transaction_count,
    COUNT(DISTINCT account_code) AS unique_accounts,
    SUM(debit_amount) AS total_debits,
    SUM(credit_amount) AS total_credits,
    COUNT(DISTINCT vendor_name) FILTER (WHERE vendor_name IS NOT NULL) AS unique_vendors,
    COUNT(DISTINCT customer_name) FILTER (WHERE customer_name IS NOT NULL) AS unique_customers
FROM qb_journal_entries
GROUP BY DATE_TRUNC('month', transaction_date)
ORDER BY month DESC;

COMMENT ON VIEW qb_monthly_summary IS 
'Monthly rollup of journal activity showing transaction volume and participant counts.';

-- =================================================================
-- VERIFICATION QUERIES
-- =================================================================

-- Test journal_clean view
SELECT 'journal_clean view test' AS check_name,
       COUNT(*) AS record_count
FROM journal_clean;

-- Test qb_active_accounts view
SELECT 'qb_active_accounts view test' AS check_name,
       COUNT(*) AS active_accounts
FROM qb_active_accounts;

-- Show account category breakdown
SELECT 'Account categories:' AS info,
       account_category, 
       COUNT(*) AS account_count
FROM qb_active_accounts
GROUP BY account_category
ORDER BY account_category;

-- Test qb_journal_with_accounts view
SELECT 'qb_journal_with_accounts test' AS check_name,
       COUNT(*) AS record_count
FROM qb_journal_with_accounts;

-- Test transaction type summary
SELECT 'Top 5 transaction types:' AS info,
       transaction_type,
       transaction_count
FROM qb_transaction_type_summary
LIMIT 5;

-- Test account activity summary (top 10 by transaction count)
SELECT 'Top 10 most active accounts:' AS info,
       account_number || ' · ' || account_name AS account,
       transaction_count,
       net_amount
FROM qb_account_activity_summary
WHERE transaction_count > 0
ORDER BY transaction_count DESC
LIMIT 10;

-- Test monthly summary (last 6 months)
SELECT 'Last 6 months activity:' AS info,
       TO_CHAR(month, 'YYYY-MM') AS month,
       transaction_count,
       unique_accounts
FROM qb_monthly_summary
ORDER BY month DESC
LIMIT 6;

-- =================================================================
-- COMPLETION MESSAGE
-- =================================================================
SELECT '✓ Phase 1 Views Created Successfully!' AS status,
       'All QB reporting views ready' AS detail;
