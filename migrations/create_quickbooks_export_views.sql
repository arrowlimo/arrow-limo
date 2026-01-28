-- ============================================================================
-- QuickBooks Export Views - Maps ALMS Data to QuickBooks Column Names
-- ============================================================================
-- Purpose: Create views with QuickBooks-compatible column names for export
-- Strategy: Non-destructive mapping - original tables unchanged
-- Date: October 19, 2025
-- ============================================================================

-- ============================================================================
-- 1. CHART OF ACCOUNTS EXPORT VIEW
-- ============================================================================
CREATE OR REPLACE VIEW qb_export_chart_of_accounts AS
SELECT
    account_number AS "Account",
    account_name AS "Name",
    CASE 
        WHEN account_type ILIKE '%asset%' THEN 'Bank'
        WHEN account_type ILIKE '%liability%' THEN 'Other Current Liability'
        WHEN account_type ILIKE '%equity%' THEN 'Equity'
        WHEN account_type ILIKE '%income%' OR account_type ILIKE '%revenue%' THEN 'Income'
        WHEN account_type ILIKE '%expense%' OR account_type ILIKE '%cost%' THEN 'Expense'
        ELSE 'Other Current Asset'
    END AS "Type",
    description AS "Description",
    CASE WHEN is_active THEN 'Active' ELSE 'Inactive' END AS "Account Status"
FROM chart_of_accounts
WHERE account_number IS NOT NULL
ORDER BY account_number;

COMMENT ON VIEW qb_export_chart_of_accounts IS 
'QuickBooks-compatible Chart of Accounts export with standard QB column names';

-- ============================================================================
-- 2. GENERAL JOURNAL EXPORT VIEW
-- ============================================================================
CREATE OR REPLACE VIEW qb_export_general_journal AS
SELECT
    transaction_id AS "Transaction ID",
    transaction_date AS "Date",
    account_number AS "Account",
    memo_description AS "Memo",
    debit AS "Debit",
    credit AS "Credit",
    num AS "Ref No.",
    source_file AS "Source"
FROM general_ledger
WHERE transaction_date IS NOT NULL
ORDER BY transaction_date, transaction_id;

COMMENT ON VIEW qb_export_general_journal IS 
'QuickBooks-compatible General Journal with standard QB column names';

-- ============================================================================
-- 3. CUSTOMER LIST EXPORT VIEW
-- ============================================================================
CREATE OR REPLACE VIEW qb_export_customers AS
SELECT
    client_id AS "Customer ID",
    COALESCE(company_name, client_name) AS "Customer",
    company_name AS "Company",
    email AS "Email",
    primary_phone AS "Phone",
    address_line1 AS "Billing Address",
    city AS "City",
    province AS "State/Province",
    zip_code AS "Zip/Postal Code",
    COALESCE(country, 'Canada') AS "Country",
    account_number AS "Account Number",
    CASE WHEN is_inactive = false THEN 'Active' ELSE 'Inactive' END AS "Status"
FROM clients
WHERE client_id IS NOT NULL
ORDER BY company_name, client_name;

COMMENT ON VIEW qb_export_customers IS 
'QuickBooks-compatible Customer List with standard QB column names';

-- ============================================================================
-- 4. VENDOR LIST EXPORT VIEW
-- ============================================================================
-- Note: suppliers table structure seems corrupted, using general_ledger supplier info
CREATE OR REPLACE VIEW qb_export_vendors AS
SELECT DISTINCT
    ROW_NUMBER() OVER (ORDER BY supplier) AS "Vendor ID",
    supplier AS "Vendor",
    supplier AS "Contact",
    NULL AS "Email",
    NULL AS "Phone",
    NULL AS "Address",
    NULL AS "City",
    NULL AS "State/Province",
    NULL AS "Zip/Postal Code",
    'Canada' AS "Country",
    NULL AS "Account Number",
    'Active' AS "Status"
FROM general_ledger
WHERE supplier IS NOT NULL AND supplier != ''
ORDER BY supplier;

COMMENT ON VIEW qb_export_vendors IS 
'QuickBooks-compatible Vendor List with standard QB column names';

-- ============================================================================
-- 5. EMPLOYEE LIST EXPORT VIEW
-- ============================================================================
CREATE OR REPLACE VIEW qb_export_employees AS
SELECT
    employee_id AS "Employee ID",
    COALESCE(full_name, first_name || ' ' || last_name) AS "Employee",
    first_name AS "First Name",
    last_name AS "Last Name",
    email AS "Email",
    phone AS "Phone",
    t4_sin AS "Social Insurance Number",
    hire_date AS "Hire Date",
    NULL AS "Release Date",
    position AS "Title",
    CASE WHEN employment_status = 'active' THEN 'Active' ELSE 'Inactive' END AS "Status"
FROM employees
WHERE employee_id IS NOT NULL
ORDER BY last_name, first_name;

COMMENT ON VIEW qb_export_employees IS 
'QuickBooks-compatible Employee List with standard QB column names';

-- ============================================================================
-- 6. ACCOUNTS RECEIVABLE AGING EXPORT VIEW
-- ============================================================================
CREATE OR REPLACE VIEW qb_export_ar_aging AS
SELECT
    client_id AS "Customer ID",
    company_name AS "Customer",
    balance AS "Balance",
    CASE 
        WHEN aging_bucket = 'current' OR days_outstanding <= 30 THEN balance
        ELSE 0
    END AS "Current",
    CASE 
        WHEN aging_bucket = '31-60' OR (days_outstanding > 30 AND days_outstanding <= 60) THEN balance
        ELSE 0
    END AS "1-30",
    CASE 
        WHEN aging_bucket = '61-90' OR (days_outstanding > 60 AND days_outstanding <= 90) THEN balance
        ELSE 0
    END AS "31-60",
    CASE 
        WHEN aging_bucket = 'over 90' OR days_outstanding > 90 THEN balance
        ELSE 0
    END AS "61-90",
    days_outstanding AS "Days Outstanding"
FROM client_aging_report
WHERE balance > 0
ORDER BY days_outstanding DESC, company_name;

COMMENT ON VIEW qb_export_ar_aging IS 
'QuickBooks-compatible A/R Aging with standard QB aging buckets';

-- ============================================================================
-- 7. PROFIT & LOSS EXPORT VIEW
-- ============================================================================
CREATE OR REPLACE VIEW qb_export_profit_loss AS
WITH income_accounts AS (
    SELECT 
        account_number AS "Account",
        account_name AS "Name",
        SUM(COALESCE(credit, 0) - COALESCE(debit, 0)) AS "Amount",
        'Income' AS "Category"
    FROM general_ledger gl
    WHERE account_type ILIKE '%income%' 
       OR account_type ILIKE '%revenue%'
    GROUP BY account_number, account_name
),
expense_accounts AS (
    SELECT 
        account_number AS "Account",
        account_name AS "Name",
        SUM(COALESCE(debit, 0) - COALESCE(credit, 0)) AS "Amount",
        'Expense' AS "Category"
    FROM general_ledger gl
    WHERE account_type ILIKE '%expense%' 
       OR account_type ILIKE '%cost%'
    GROUP BY account_number, account_name
)
SELECT * FROM income_accounts
UNION ALL
SELECT * FROM expense_accounts
ORDER BY "Category", "Account";

COMMENT ON VIEW qb_export_profit_loss IS 
'QuickBooks-compatible Profit & Loss with Income and Expense categorization';

-- ============================================================================
-- 8. BALANCE SHEET EXPORT VIEW
-- ============================================================================
CREATE OR REPLACE VIEW qb_export_balance_sheet AS
WITH assets AS (
    SELECT 
        account_number AS "Account",
        account_name AS "Name",
        SUM(COALESCE(debit, 0) - COALESCE(credit, 0)) AS "Amount",
        'Asset' AS "Category"
    FROM general_ledger gl
    WHERE account_type ILIKE '%asset%'
    GROUP BY account_number, account_name
),
liabilities AS (
    SELECT 
        account_number AS "Account",
        account_name AS "Name",
        SUM(COALESCE(credit, 0) - COALESCE(debit, 0)) AS "Amount",
        'Liability' AS "Category"
    FROM general_ledger gl
    WHERE account_type ILIKE '%liability%'
    GROUP BY account_number, account_name
),
equity AS (
    SELECT 
        account_number AS "Account",
        account_name AS "Name",
        SUM(COALESCE(credit, 0) - COALESCE(debit, 0)) AS "Amount",
        'Equity' AS "Category"
    FROM general_ledger gl
    WHERE account_type ILIKE '%equity%'
    GROUP BY account_number, account_name
)
SELECT * FROM assets
UNION ALL
SELECT * FROM liabilities
UNION ALL
SELECT * FROM equity
ORDER BY "Category", "Account";

COMMENT ON VIEW qb_export_balance_sheet IS 
'QuickBooks-compatible Balance Sheet with Assets, Liabilities, and Equity';

-- ============================================================================
-- 9. VEHICLE LIST EXPORT VIEW
-- ============================================================================
CREATE OR REPLACE VIEW qb_export_vehicles AS
SELECT
    vehicle_id AS "Vehicle ID",
    COALESCE(vehicle_number, make || ' ' || model) AS "Vehicle",
    make AS "Make",
    model AS "Model",
    year AS "Year",
    vin_number AS "VIN",
    license_plate AS "License Plate",
    commission_date AS "Purchase Date",
    NULL::numeric AS "Purchase Price",
    CASE WHEN is_active THEN 'Active' ELSE 'Inactive' END AS "Status"
FROM vehicles
WHERE vehicle_id IS NOT NULL
ORDER BY vehicle_number, make, model;

COMMENT ON VIEW qb_export_vehicles IS 
'QuickBooks-compatible Vehicle List for fixed asset tracking';

-- ============================================================================
-- 10. INVOICE EXPORT VIEW (Using charters as invoices)
-- ============================================================================
CREATE OR REPLACE VIEW qb_export_invoices AS
SELECT
    charter_id AS "Invoice #",
    client_id AS "Customer ID",
    charter_date AS "Date",
    charter_date + INTERVAL '30 days' AS "Due Date",
    total_amount_due AS "Amount",
    deposit AS "Paid",
    (COALESCE(total_amount_due, 0) - COALESCE(deposit, 0)) AS "Balance",
    CASE 
        WHEN status = 'paid' OR balance = 0 THEN 'Paid'
        WHEN deposit > 0 AND balance > 0 THEN 'Partial'
        WHEN balance > 0 THEN 'Open'
        ELSE 'Open'
    END AS "Status",
    notes AS "Memo"
FROM charters
WHERE charter_date IS NOT NULL
ORDER BY charter_date DESC;

COMMENT ON VIEW qb_export_invoices IS 
'QuickBooks-compatible Invoice List with payment status';

-- ============================================================================
-- EXPORT SUMMARY VIEW
-- ============================================================================
CREATE OR REPLACE VIEW qb_export_summary AS
SELECT 
    'Chart of Accounts' AS "Export View",
    COUNT(*) AS "Record Count",
    'qb_export_chart_of_accounts' AS "View Name"
FROM qb_export_chart_of_accounts
UNION ALL
SELECT 'General Journal', COUNT(*), 'qb_export_general_journal' FROM qb_export_general_journal
UNION ALL
SELECT 'Customers', COUNT(*), 'qb_export_customers' FROM qb_export_customers
UNION ALL
SELECT 'Vendors', COUNT(*), 'qb_export_vendors' FROM qb_export_vendors
UNION ALL
SELECT 'Employees', COUNT(*), 'qb_export_employees' FROM qb_export_employees
UNION ALL
SELECT 'A/R Aging', COUNT(*), 'qb_export_ar_aging' FROM qb_export_ar_aging
UNION ALL
SELECT 'Vehicles', COUNT(*), 'qb_export_vehicles' FROM qb_export_vehicles
UNION ALL
SELECT 'Invoices', COUNT(*), 'qb_export_invoices' FROM qb_export_invoices;

COMMENT ON VIEW qb_export_summary IS 
'Summary of all QuickBooks export views with record counts';

-- ============================================================================
-- USAGE INSTRUCTIONS
-- ============================================================================
-- 
-- To export data to QuickBooks format:
-- 
-- 1. Query any qb_export_* view
-- 2. Export to CSV
-- 3. Import CSV into QuickBooks using standard import tool
-- 
-- Examples:
-- 
--   COPY qb_export_chart_of_accounts TO 'L:\limo\qb_exports\chart_of_accounts.csv' CSV HEADER;
--   COPY qb_export_general_journal TO 'L:\limo\qb_exports\journal.csv' CSV HEADER;
--   COPY qb_export_customers TO 'L:\limo\qb_exports\customers.csv' CSV HEADER;
-- 
-- Or from Python:
-- 
--   import pandas as pd
--   df = pd.read_sql("SELECT * FROM qb_export_chart_of_accounts", conn)
--   df.to_csv("chart_of_accounts.csv", index=False)
--
-- ============================================================================
