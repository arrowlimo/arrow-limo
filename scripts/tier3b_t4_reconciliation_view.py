#!/usr/bin/env python
"""TIER 3B: Create t4_vs_payroll_reconciliation view.
Compare calculated pay periods vs T4 reported amounts.
Identifies variances and data quality issues.
"""
import psycopg2
import os

DB_HOST=os.environ.get("DB_HOST","localhost")
DB_NAME=os.environ.get("DB_NAME","almsdata")
DB_USER=os.environ.get("DB_USER","postgres")
DB_PASSWORD=os.environ.get("DB_PASSWORD","***REMOVED***")

conn=psycopg2.connect(host=DB_HOST,database=DB_NAME,user=DB_USER,password=DB_PASSWORD)
cur=conn.cursor()

print("\n"+"="*100)
print("TIER 3B: CREATE T4_VS_PAYROLL_RECONCILIATION VIEW")
print("="*100)
print()

# Drop if exists
cur.execute("DROP VIEW IF EXISTS t4_vs_payroll_reconciliation CASCADE")
print("✅ Dropped existing view")

# Create reconciliation view
cur.execute("""
    CREATE VIEW t4_vs_payroll_reconciliation AS
    SELECT 
        -- IDs
        t.t4_id,
        t.employee_id,
        e.full_name,
        t.fiscal_year,
        
        -- T4 reported amounts (ground truth)
        t.t4_employment_income as t4_reported_income,
        t.t4_federal_tax as t4_reported_fed_tax,
        t.t4_provincial_tax as t4_reported_prov_tax,
        t.t4_cpp_contributions as t4_reported_cpp,
        t.t4_ei_contributions as t4_reported_ei,
        COALESCE(t.t4_federal_tax,0) + COALESCE(t.t4_provincial_tax,0) 
            + COALESCE(t.t4_cpp_contributions,0) + COALESCE(t.t4_ei_contributions,0) as t4_total_deductions,
        
        -- Calculated from pay periods
        SUM(COALESCE(epc.gross_income_before_deductions,0)) as calculated_income,
        SUM(COALESCE(epc.federal_tax_calc,0)) as calculated_fed_tax,
        SUM(COALESCE(epc.provincial_tax_calc,0)) as calculated_prov_tax,
        SUM(COALESCE(epc.cpp_employee_calc,0)) as calculated_cpp,
        SUM(COALESCE(epc.ei_employee_calc,0)) as calculated_ei,
        SUM(COALESCE(epc.federal_tax_calc,0) + COALESCE(epc.provincial_tax_calc,0)
            + COALESCE(epc.cpp_employee_calc,0) + COALESCE(epc.ei_employee_calc,0)) as calculated_total_deductions,
        
        -- Variances
        COALESCE(t.t4_employment_income,0) - SUM(COALESCE(epc.gross_income_before_deductions,0)) as income_variance,
        ABS(COALESCE(t.t4_employment_income,0) - SUM(COALESCE(epc.gross_income_before_deductions,0))) as income_variance_abs,
        
        COALESCE(t.t4_federal_tax,0) - SUM(COALESCE(epc.federal_tax_calc,0)) as fed_tax_variance,
        COALESCE(t.t4_provincial_tax,0) - SUM(COALESCE(epc.provincial_tax_calc,0)) as prov_tax_variance,
        COALESCE(t.t4_cpp_contributions,0) - SUM(COALESCE(epc.cpp_employee_calc,0)) as cpp_variance,
        COALESCE(t.t4_ei_contributions,0) - SUM(COALESCE(epc.ei_employee_calc,0)) as ei_variance,
        
        -- Data quality metrics
        t.confidence_level as t4_confidence,
        t.source as t4_source,
        COUNT(DISTINCT epc.pay_period_id) as periods_with_pay_data,
        CASE WHEN COUNT(DISTINCT epc.pay_period_id) >= 26 THEN 100
             WHEN COUNT(DISTINCT epc.pay_period_id) >= 24 THEN 90
             WHEN COUNT(DISTINCT epc.pay_period_id) >= 20 THEN 75
             ELSE 50 END as period_coverage_percent,
        
        -- Status
        CASE 
            WHEN ABS(COALESCE(t.t4_employment_income,0) - SUM(COALESCE(epc.gross_income_before_deductions,0))) < 100 
                THEN '✅ MATCH'
            WHEN ABS(COALESCE(t.t4_employment_income,0) - SUM(COALESCE(epc.gross_income_before_deductions,0))) < 1000 
                THEN '🟡 MINOR_VARIANCE'
            WHEN ABS(COALESCE(t.t4_employment_income,0) - SUM(COALESCE(epc.gross_income_before_deductions,0))) < 5000 
                THEN '🔴 MODERATE_VARIANCE'
            ELSE '❌ MAJOR_VARIANCE'
        END as reconciliation_status
        
    FROM employee_t4_summary t
    JOIN employees e ON t.employee_id = e.employee_id
    LEFT JOIN employee_pay_calc epc ON t.employee_id = epc.employee_id 
        AND t.fiscal_year = epc.fiscal_year
    GROUP BY 
        t.t4_id, t.employee_id, e.full_name, t.fiscal_year,
        t.t4_employment_income, t.t4_federal_tax, t.t4_provincial_tax,
        t.t4_cpp_contributions, t.t4_ei_contributions,
        t.confidence_level, t.source
""")
print("✅ Created t4_vs_payroll_reconciliation view")

# Show reconciliation results
print("\n2024 T4 vs Payroll Reconciliation:")
print("-" * 100)
cur.execute("""
    SELECT 
        full_name,
        t4_reported_income,
        calculated_income,
        income_variance,
        periods_with_pay_data,
        reconciliation_status
    FROM t4_vs_payroll_reconciliation
    WHERE fiscal_year = 2024
    ORDER BY income_variance_abs DESC
""")
print("Employee | T4 Income | Calculated | Variance | Periods | Status")
print("-" * 100)
for name, t4, calc, var, periods, status in cur.fetchall():
    print(f"{name:<30} | ${t4:>12,.0f} | ${calc:>10,.0f} | ${var:>10,.0f} | {periods:>2}/26 | {status}")

# Summary statistics
print("\n2024 Reconciliation Summary:")
print("-" * 100)
cur.execute("""
    SELECT 
        COUNT(*) as total_employees,
        COUNT(CASE WHEN reconciliation_status = '✅ MATCH' THEN 1 END) as perfect_match,
        COUNT(CASE WHEN reconciliation_status = '🟡 MINOR_VARIANCE' THEN 1 END) as minor_variance,
        COUNT(CASE WHEN reconciliation_status = '🔴 MODERATE_VARIANCE' THEN 1 END) as moderate_variance,
        COUNT(CASE WHEN reconciliation_status = '❌ MAJOR_VARIANCE' THEN 1 END) as major_variance,
        
        SUM(t4_reported_income) as total_t4_income,
        SUM(calculated_income) as total_calculated,
        SUM(income_variance) as total_variance,
        
        AVG(period_coverage_percent) as avg_period_coverage
    FROM t4_vs_payroll_reconciliation
    WHERE fiscal_year = 2024
""")
total, perfect, minor, moderate, major, t4_tot, calc_tot, var_tot, coverage = cur.fetchone()
print(f"Employees: {total}")
print(f"  - Perfect match: {perfect} ({100*perfect/total:.0f}%)")
print(f"  - Minor variance: {minor} ({100*minor/total:.0f}%)")
print(f"  - Moderate variance: {moderate} ({100*moderate/total:.0f}%)")
print(f"  - Major variance: {major} ({100*major/total:.0f}%)")
print(f"\nFinancial:")
print(f"  T4 reported total: ${t4_tot:,.2f}")
print(f"  Calculated total: ${calc_tot:,.2f}")
print(f"  Net variance: ${var_tot:,.2f}")
print(f"  Avg period coverage: {coverage:.0f}%")

# Identify high-variance cases
print("\n⚠️  High Variance Cases (Needs Investigation):")
print("-" * 100)
cur.execute("""
    SELECT 
        full_name,
        t4_reported_income,
        calculated_income,
        income_variance,
        periods_with_pay_data,
        t4_source,
        reconciliation_status
    FROM t4_vs_payroll_reconciliation
    WHERE fiscal_year = 2024 
      AND reconciliation_status IN ('🔴 MODERATE_VARIANCE', '❌ MAJOR_VARIANCE')
    ORDER BY income_variance_abs DESC
""")
high_var = cur.fetchall()
if high_var:
    for name, t4, calc, var, periods, source, status in high_var:
        print(f"{name:<30} | T4: ${t4:>12,.0f} | Calc: ${calc:>10,.0f} | Var: ${var:>10,.0f} | {periods}/26 | {source} | {status}")
else:
    print("✅ No high-variance cases found!")

conn.commit()
cur.close()
conn.close()

print("\n✅ TIER 3B COMPLETE - T4 RECONCILIATION VIEW CREATED!")
