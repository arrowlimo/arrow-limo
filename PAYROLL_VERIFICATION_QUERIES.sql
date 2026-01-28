-- PAYROLL SYSTEM VERIFICATION QUERIES
-- Run these queries to verify all components are working correctly
-- Generated: 2026-01-18

-- ========================================
-- 1. VERIFY PAY PERIODS STRUCTURE
-- ========================================

-- Count pay periods by year
SELECT fiscal_year, COUNT(*) as period_count
FROM pay_periods
GROUP BY fiscal_year
ORDER BY fiscal_year DESC;

-- Sample pay periods (first 5 of 2024)
SELECT 
    pay_period_id,
    fiscal_year,
    period_number,
    period_start_date,
    period_end_date,
    pay_date
FROM pay_periods
WHERE fiscal_year = 2024
ORDER BY period_number
LIMIT 5;

-- ========================================
-- 2. VERIFY EMPLOYEE_PAY_MASTER POPULATION
-- ========================================

-- Total records and coverage
SELECT 
    COUNT(*) as total_records,
    COUNT(DISTINCT employee_id) as employees,
    COUNT(DISTINCT pay_period_id) as periods,
    COUNT(DISTINCT fiscal_year) as years,
    SUM(charter_hours_sum) as total_hours,
    SUM(gross_pay) as total_gross,
    SUM(gratuity_amount) as total_gratuity,
    AVG(data_completeness) as avg_completeness
FROM employee_pay_master;

-- Sample records (2024, all columns)
SELECT 
    e.name,
    pp.fiscal_year,
    pp.period_number,
    epm.charter_hours_sum,
    epm.base_pay,
    epm.gratuity_amount,
    epm.federal_tax,
    epm.provincial_tax,
    epm.cpp_employee,
    epm.ei_employee,
    epm.gross_pay,
    epm.net_pay,
    epm.data_completeness,
    epm.confidence_level
FROM employee_pay_master epm
JOIN employees e ON epm.employee_id = e.employee_id
JOIN pay_periods pp ON epm.pay_period_id = pp.pay_period_id
WHERE pp.fiscal_year = 2024
LIMIT 10;

-- ========================================
-- 3. VERIFY TAX CALCULATIONS
-- ========================================

-- 2024 annual tax summary
SELECT 
    e.name,
    COUNT(DISTINCT epm.pay_period_id) as pay_periods,
    SUM(epm.charter_hours_sum) as total_hours,
    SUM(epm.base_pay) as total_base,
    SUM(epm.gratuity_amount) as total_gratuity,
    SUM(epm.gross_pay) as total_gross,
    SUM(epm.federal_tax) as federal_tax,
    SUM(epm.provincial_tax) as provincial_tax,
    SUM(epm.cpp_employee) as cpp_contrib,
    SUM(epm.ei_employee) as ei_contrib,
    SUM(epm.net_pay) as net_pay,
    ROUND(100.0 * (SUM(epm.federal_tax) + SUM(epm.provincial_tax)) / NULLIF(SUM(epm.gross_pay), 0), 1) as tax_rate_pct
FROM employee_pay_master epm
JOIN employees e ON epm.employee_id = e.employee_id
JOIN pay_periods pp ON epm.pay_period_id = pp.pay_period_id
WHERE pp.fiscal_year = 2024
GROUP BY e.employee_id, e.name
ORDER BY total_gross DESC;

-- ========================================
-- 4. VERIFY T4 RECONCILIATION
-- ========================================

-- T4 vs Payroll reconciliation (2024)
SELECT 
    e.name,
    t4.t4_employment_income as t4_reported,
    SUM(epm.gross_pay) as calculated_from_periods,
    ROUND(t4.t4_employment_income - SUM(epm.gross_pay), 2) as variance,
    CASE
        WHEN ABS(t4.t4_employment_income - SUM(epm.gross_pay)) < 100 THEN '✅ MATCH'
        WHEN ABS(t4.t4_employment_income - SUM(epm.gross_pay)) < 1000 THEN '🟡 MINOR'
        WHEN ABS(t4.t4_employment_income - SUM(epm.gross_pay)) < 5000 THEN '🔴 MODERATE'
        ELSE '❌ MAJOR'
    END as status,
    COUNT(DISTINCT epm.pay_period_id) as periods_with_data
FROM employee_t4_summary t4
LEFT JOIN employees e ON t4.employee_id = e.employee_id
LEFT JOIN employee_pay_master epm ON epm.employee_id = t4.employee_id
LEFT JOIN pay_periods pp ON epm.pay_period_id = pp.pay_period_id AND pp.fiscal_year = t4.fiscal_year
WHERE t4.fiscal_year = 2024
GROUP BY e.employee_id, e.name, t4.t4_employment_income
ORDER BY t4.t4_employment_income DESC;

-- ========================================
-- 5. VERIFY CHARTER LINKAGE QUALITY
-- ========================================

-- Drivers with hours
SELECT 
    COUNT(DISTINCT employee_id) as drivers_with_hours,
    COUNT(DISTINCT charter_id) as charters_with_hours,
    SUM(driver_hours_worked) as total_hours,
    AVG(driver_hours_worked) as avg_hours_per_charter
FROM charters
WHERE driver_hours_worked > 0 
  AND assigned_driver_id IS NOT NULL;

-- Drivers without proper rates (should be 0)
SELECT 
    COUNT(DISTINCT e.employee_id) as drivers_without_rate
FROM employees e
LEFT JOIN employee_t4_summary t4 ON e.employee_id = t4.employee_id AND t4.fiscal_year = 2024
WHERE e.employee_type IN ('driver', 'dispatcher')
  AND e.is_active = TRUE
  AND t4.employee_id IS NULL;  -- No T4 record means no pay data

-- ========================================
-- 6. VERIFY YEAR-BASED VIEWS WORK
-- ========================================

-- Sample: Receipts for 2024
SELECT COUNT(*) as count_2024_receipts FROM receipts_2024;

-- Sample: Banking transactions for 2024
SELECT COUNT(*) as count_2024_banking FROM banking_transactions_2024;

-- Sample: GL entries for 2024
SELECT COUNT(*) as count_2024_gl FROM general_ledger_2024;

-- Sample: Payments for 2024
SELECT COUNT(*) as count_2024_payments FROM payments_2024;

-- Sample: Charters for 2024
SELECT COUNT(*) as count_2024_charters FROM charters_2024;

-- ========================================
-- 7. VERIFY BANKING RECONCILIATION
-- ========================================

-- Total banking transactions and receipt linkage
SELECT 
    COUNT(*) as total_banking_txns,
    COUNT(DISTINCT receipt_id) as txns_with_receipt,
    COUNT(*) - COUNT(DISTINCT receipt_id) as txns_without_receipt,
    ROUND(100.0 * COUNT(DISTINCT receipt_id) / COUNT(*), 1) as pct_linked
FROM banking_transactions;

-- ========================================
-- 8. DATA QUALITY METRICS
-- ========================================

-- Charter data quality for 2024
SELECT 
    COUNT(*) as total_charters_2024,
    COUNT(CASE WHEN driver_hours_worked > 0 THEN 1 END) as charters_with_hours,
    COUNT(CASE WHEN assigned_driver_id IS NOT NULL THEN 1 END) as charters_with_driver,
    ROUND(100.0 * COUNT(CASE WHEN driver_hours_worked > 0 THEN 1 END) / COUNT(*), 1) as pct_with_hours
FROM charters
WHERE EXTRACT(YEAR FROM charter_date) = 2024;

-- Employee pay_master data quality
SELECT 
    AVG(data_completeness) as avg_completeness,
    MIN(data_completeness) as min_completeness,
    MAX(data_completeness) as max_completeness,
    COUNT(CASE WHEN data_completeness < 50 THEN 1 END) as low_quality_records,
    COUNT(CASE WHEN data_completeness >= 90 THEN 1 END) as high_quality_records
FROM employee_pay_master;

-- ========================================
-- 9. AUDIT TRAIL VERIFICATION
-- ========================================

-- Show data sources used in payroll
SELECT 
    DISTINCT data_source,
    COUNT(*) as record_count,
    AVG(confidence_level) as avg_confidence
FROM employee_pay_master
WHERE data_source IS NOT NULL
GROUP BY data_source;

-- Show confidence levels distribution
SELECT 
    confidence_level,
    COUNT(*) as record_count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM employee_pay_master), 1) as pct_of_total
FROM employee_pay_master
GROUP BY confidence_level
ORDER BY confidence_level DESC;

-- ========================================
-- 10. READY-FOR-AUDIT VERIFICATION
-- ========================================

-- Final audit checklist
SELECT 
    'Banking Reconciliation' as component,
    ROUND(100.0 * COUNT(DISTINCT receipt_id) / COUNT(*), 1) as pct_complete
FROM banking_transactions
UNION ALL
SELECT 
    'Employee Pay Master Population',
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM pay_periods), 1)
FROM employee_pay_master
UNION ALL
SELECT 
    'T4 Records for 2024',
    COUNT(*)
FROM employee_t4_summary
WHERE fiscal_year = 2024
UNION ALL
SELECT 
    'Year-Based Accounting Views',
    (SELECT COUNT(*) FROM information_schema.views 
     WHERE table_schema = 'public' 
     AND table_name LIKE '%_202%')  -- Rough count of year-based views
;

-- ========================================
-- QUERIES COMPLETE
-- ========================================
-- All verification queries above are ready to run
-- Copy and paste any query into your SQL client to verify data
-- Expected results documented in SESSION_SUMMARY_PAYROLL_2026-01-18.md
