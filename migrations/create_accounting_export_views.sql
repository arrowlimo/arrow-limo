-- Accounting export views (qb_export_*)
--
-- The Reports "Accounting Exports" tab (frontend/src/views/Reports.vue) renders a
-- card per view named qb_export_<name> and downloads each as CSV via
-- reports.py:export_accounting_view (which runs `SELECT * FROM <view>`, optionally
-- range-filtering a quoted "Date" column). reports.py referenced this migration by
-- name but it was missing from the repo, so the feature reported "not_initialized".
--
-- These views are read-only mappings of the existing accounting tables onto the
-- exact view names the UI requests. Column aliases are export-ready headers; no
-- accounting figures are invented — Chart of Accounts / P&L / Balance Sheet read
-- the real balances stored on chart_of_accounts, A/R Aging reads client_aging_report,
-- and the General Journal reads general_ledger.
--
-- Safe and reversible: CREATE OR REPLACE VIEW touches no table data; drop any with
-- DROP VIEW IF EXISTS qb_export_<name>.

-- Remove earlier generic placeholders if present (superseded by the named set).
DROP VIEW IF EXISTS qb_export_payments;
DROP VIEW IF EXISTS qb_export_receipts;
DROP VIEW IF EXISTS qb_export_banking_transactions;

-- Chart of Accounts
CREATE OR REPLACE VIEW qb_export_chart_of_accounts AS
SELECT
    account_code      AS "Account Code",
    account_name      AS "Account Name",
    account_type      AS "Type",
    qb_account_type   AS "QB Type",
    normal_balance    AS "Normal Balance",
    current_balance   AS "Balance",
    description       AS "Description",
    is_active         AS "Active"
FROM chart_of_accounts
ORDER BY account_code;

-- General Journal (full ledger; "Date" enables range filtering)
CREATE OR REPLACE VIEW qb_export_general_journal AS
SELECT
    g.date              AS "Date",
    g.num               AS "Num",
    g.transaction_type  AS "Transaction Type",
    g.name              AS "Name",
    g.account           AS "Account",
    g.account_name      AS "Account Name",
    g.debit             AS "Debit",
    g.credit            AS "Credit",
    g.memo_description  AS "Memo"
FROM general_ledger g
ORDER BY g.date;

-- Customer list
CREATE OR REPLACE VIEW qb_export_customers AS
SELECT
    account_number                                              AS "Account Number",
    COALESCE(NULLIF(client_name, ''), NULLIF(company_name, ''),
             NULLIF(name, ''))                                  AS "Customer Name",
    COALESCE(primary_phone, phone, cell_phone)                  AS "Phone",
    email                                                       AS "Email",
    COALESCE(address_line1, address)                            AS "Address",
    city                                                        AS "City",
    COALESCE(state, province)                                   AS "Province",
    zip_code                                                    AS "Postal Code",
    balance                                                     AS "Balance",
    status                                                      AS "Status"
FROM clients
ORDER BY account_number;

-- Vendor list
CREATE OR REPLACE VIEW qb_export_vendors AS
SELECT
    COALESCE(NULLIF(display_name, ''), canonical_vendor)  AS "Vendor Name",
    canonical_vendor                                      AS "Canonical Vendor",
    contact_email                                         AS "Email",
    payment_terms                                         AS "Payment Terms",
    default_gl_code                                       AS "Default GL Code",
    default_category                                      AS "Default Category",
    status                                                AS "Status"
FROM vendor_accounts
ORDER BY 1;

-- Employee list
CREATE OR REPLACE VIEW qb_export_employees AS
SELECT
    employee_number                                            AS "Employee Number",
    COALESCE(NULLIF(full_name, ''),
             NULLIF(TRIM(COALESCE(first_name, '') || ' '
                        || COALESCE(last_name, '')), ''))      AS "Employee Name",
    position                                                   AS "Position",
    COALESCE(phone, cell_phone)                                AS "Phone",
    email                                                      AS "Email",
    hire_date                                                  AS "Hire Date",
    employment_status                                          AS "Status"
FROM employees
ORDER BY 2;

-- A/R Aging
CREATE OR REPLACE VIEW qb_export_ar_aging AS
SELECT
    account_number     AS "Account Number",
    company_name       AS "Customer Name",
    balance            AS "Balance",
    days_outstanding   AS "Days Outstanding",
    aging_bucket       AS "Aging Bucket",
    risk_level         AS "Risk Level"
FROM client_aging_report
ORDER BY balance DESC;

-- Profit & Loss (income-statement accounts and their balances)
CREATE OR REPLACE VIEW qb_export_profit_loss AS
SELECT
    account_code     AS "Account Code",
    account_name     AS "Account Name",
    account_type     AS "Type",
    current_balance  AS "Amount"
FROM chart_of_accounts
WHERE LOWER(account_type) IN ('income', 'revenue', 'expense', 'cogs')
ORDER BY account_type, account_code;

-- Balance Sheet (asset / liability / equity accounts and their balances)
CREATE OR REPLACE VIEW qb_export_balance_sheet AS
SELECT
    account_code     AS "Account Code",
    account_name     AS "Account Name",
    account_type     AS "Type",
    current_balance  AS "Amount"
FROM chart_of_accounts
WHERE LOWER(account_type) LIKE '%asset%'
   OR LOWER(account_type) LIKE '%liabilit%'
   OR LOWER(account_type) = 'equity'
ORDER BY account_type, account_code;

-- Vehicle list (fixed assets)
CREATE OR REPLACE VIEW qb_export_vehicles AS
SELECT
    vehicle_number                          AS "Vehicle Number",
    make                                    AS "Make",
    model                                   AS "Model",
    year                                    AS "Year",
    license_plate                           AS "License Plate",
    passenger_capacity                      AS "Capacity",
    vin_number                              AS "VIN",
    COALESCE(operational_status, status)    AS "Status"
FROM vehicles
ORDER BY vehicle_number;

-- Invoice list ("Date" enables range filtering)
CREATE OR REPLACE VIEW qb_export_invoices AS
SELECT
    invoice_date        AS "Date",
    invoice_number      AS "Invoice #",
    reserve_number      AS "Reserve #",
    subtotal_taxable    AS "Subtotal Taxable",
    gst_amount          AS "GST",
    invoice_total       AS "Total",
    total_payments      AS "Payments",
    balance_due         AS "Balance Due",
    invoice_status      AS "Status"
FROM invoices
ORDER BY invoice_date;
