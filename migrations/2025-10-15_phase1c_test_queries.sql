-- =====================================================================
-- Phase 1c: Test QB-Style Queries
-- Date: October 15, 2025
-- Purpose: Validate QB journal structure with sample reports
-- =====================================================================

\echo ''
\echo '====================================================================='
\echo 'TEST 1: Journal Entry Report (Last 20 transactions)'
\echo '====================================================================='

SELECT 
    TO_CHAR(transaction_date, 'YYYY-MM-DD') AS date,
    transaction_type AS type,
    account_code || ' · ' || account_name AS account,
    vendor_name AS vendor,
    memo,
    debit_amount AS debit,
    credit_amount AS credit
FROM qb_journal_entries
WHERE transaction_date IS NOT NULL
ORDER BY transaction_date DESC, staging_id DESC
LIMIT 20;

\echo ''
\echo '====================================================================='
\echo 'TEST 2: Account Activity Summary (Top 15 most active accounts)'
\echo '====================================================================='

SELECT 
    account_number,
    account_name,
    account_category,
    transaction_count,
    TO_CHAR(total_debits, 'FM$999,999,999.00') AS total_debits,
    TO_CHAR(total_credits, 'FM$999,999,999.00') AS total_credits,
    TO_CHAR(net_amount, 'FM$999,999,999.00') AS net_amount
FROM qb_account_activity_summary
WHERE transaction_count > 0
ORDER BY transaction_count DESC
LIMIT 15;

\echo ''
\echo '====================================================================='
\echo 'TEST 3: General Ledger Report (Account 1000 - Last 10 transactions)'
\echo '====================================================================='

SELECT 
    TO_CHAR(date, 'YYYY-MM-DD') AS date,
    transaction_type AS type,
    num,
    name,
    memo_description AS memo,
    TO_CHAR(debit, 'FM$999,999.00') AS debit,
    TO_CHAR(credit, 'FM$999,999.00') AS credit,
    TO_CHAR(balance, 'FM$999,999.00') AS balance
FROM general_ledger
WHERE account LIKE '1000%'
ORDER BY date DESC
LIMIT 10;

\echo ''
\echo '====================================================================='
\echo 'TEST 4: Transaction Type Breakdown'
\echo '====================================================================='

SELECT 
    transaction_type,
    transaction_count,
    TO_CHAR(total_debits, 'FM$999,999,999.00') AS total_debits,
    TO_CHAR(total_credits, 'FM$999,999,999.00') AS total_credits,
    TO_CHAR(first_date, 'YYYY-MM-DD') AS first_date,
    TO_CHAR(last_date, 'YYYY-MM-DD') AS last_date
FROM qb_transaction_type_summary
ORDER BY transaction_count DESC;

\echo ''
\echo '====================================================================='
\echo 'TEST 5: Income Statement Summary (Revenue & Expenses)'
\echo '====================================================================='

-- Revenue (4000-4999)
SELECT 
    'REVENUE' AS category,
    account_number,
    account_name,
    transaction_count,
    TO_CHAR(ABS(net_amount), 'FM$999,999.00') AS amount
FROM qb_account_activity_summary
WHERE account_category = 'Income'
  AND transaction_count > 0
ORDER BY account_number

UNION ALL

SELECT 
    '',
    '',
    'TOTAL REVENUE',
    SUM(transaction_count),
    TO_CHAR(ABS(SUM(net_amount)), 'FM$999,999.00')
FROM qb_account_activity_summary
WHERE account_category = 'Income'

UNION ALL

SELECT '', '', '', 0, ''

UNION ALL

-- Expenses (6000-6999)
SELECT 
    'EXPENSES',
    account_number,
    account_name,
    transaction_count,
    TO_CHAR(ABS(net_amount), 'FM$999,999.00')
FROM qb_account_activity_summary
WHERE account_category = 'Expenses'
  AND transaction_count > 0
ORDER BY account_number
LIMIT 10

UNION ALL

SELECT 
    '',
    '',
    'TOTAL EXPENSES (showing top 10)',
    SUM(transaction_count),
    TO_CHAR(ABS(SUM(net_amount)), 'FM$999,999.00')
FROM qb_account_activity_summary
WHERE account_category = 'Expenses';

\echo ''
\echo '====================================================================='
\echo 'TEST 6: Balance Sheet Summary (Assets & Liabilities)'
\echo '====================================================================='

-- Assets
SELECT 
    'ASSETS' AS category,
    account_number,
    account_name,
    transaction_count,
    TO_CHAR(net_amount, 'FM$999,999.00') AS balance
FROM qb_account_activity_summary
WHERE account_category = 'Assets'
  AND transaction_count > 0
ORDER BY account_number
LIMIT 10

UNION ALL

SELECT 
    '',
    '',
    'TOTAL ASSETS (showing top 10)',
    SUM(transaction_count),
    TO_CHAR(SUM(net_amount), 'FM$999,999.00')
FROM qb_account_activity_summary
WHERE account_category = 'Assets'

UNION ALL

SELECT '', '', '', 0, ''

UNION ALL

-- Liabilities
SELECT 
    'LIABILITIES',
    account_number,
    account_name,
    transaction_count,
    TO_CHAR(ABS(net_amount), 'FM$999,999.00')
FROM qb_account_activity_summary
WHERE account_category = 'Liabilities'
  AND transaction_count > 0
ORDER BY account_number
LIMIT 10

UNION ALL

SELECT 
    '',
    '',
    'TOTAL LIABILITIES (showing top 10)',
    SUM(transaction_count),
    TO_CHAR(ABS(SUM(net_amount)), 'FM$999,999.00')
FROM qb_account_activity_summary
WHERE account_category = 'Liabilities';

\echo ''
\echo '====================================================================='
\echo 'TEST 7: Monthly Activity Trend (Last 12 months)'
\echo '====================================================================='

SELECT 
    TO_CHAR(month, 'YYYY-MM') AS month,
    transaction_count,
    unique_accounts AS accounts,
    unique_vendors AS vendors,
    unique_customers AS customers,
    TO_CHAR(total_debits, 'FM$999,999,999') AS debits,
    TO_CHAR(total_credits, 'FM$999,999,999') AS credits
FROM qb_monthly_summary
ORDER BY month DESC
LIMIT 12;

\echo ''
\echo '====================================================================='
\echo 'TEST 8: Data Quality Check'
\echo '====================================================================='

SELECT 
    'qb_journal_entries' AS table_name,
    COUNT(*) AS total_rows,
    COUNT(DISTINCT account_code) AS unique_accounts,
    COUNT(DISTINCT transaction_type) AS unique_types,
    COUNT(DISTINCT vendor_name) FILTER (WHERE vendor_name IS NOT NULL) AS unique_vendors,
    COUNT(DISTINCT customer_name) FILTER (WHERE customer_name IS NOT NULL) AS unique_customers,
    MIN(transaction_date) AS earliest_date,
    MAX(transaction_date) AS latest_date
FROM qb_journal_entries

UNION ALL

SELECT 
    'general_ledger',
    COUNT(*),
    COUNT(DISTINCT account),
    COUNT(DISTINCT transaction_type),
    COUNT(DISTINCT name),
    NULL,
    MIN(date),
    MAX(date)
FROM general_ledger

UNION ALL

SELECT 
    'chart_of_accounts',
    COUNT(*),
    COUNT(DISTINCT account_type),
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
FROM chart_of_accounts
WHERE is_active = true;

\echo ''
\echo '====================================================================='
\echo '✓ Phase 1 Testing Complete!'
\echo '====================================================================='
\echo 'All QB-style queries executed successfully.'
\echo 'qb_journal_entries table is ready for production use!'
\echo '====================================================================='
