#!/usr/bin/env python
"""
Comprehensive 2012 tax data test.
Verifies what data exists and what's missing for tax computations.
"""

import psycopg2
from decimal import Decimal

conn = psycopg2.connect(
    host="localhost",
    dbname="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()

print("=" * 80)
print("2012 TAX SYSTEM DATA TEST")
print("=" * 80)

# 1. Check charters (revenue/GST source)
print("\n1. CHARTERS (Revenue/GST Source)")
print("-" * 80)
cur.execute("""
    SELECT COUNT(*) AS total_charters,
           COUNT(*) FILTER (WHERE total_amount_due > 0) AS with_amount,
           COALESCE(SUM(total_amount_due), 0) AS total_revenue,
           COALESCE(SUM(total_amount_due * 0.05 / 1.05), 0) AS estimated_gst
    FROM charters
    WHERE charter_date >= '2012-01-01' AND charter_date <= '2012-12-31'
""")
r = cur.fetchone()
print(f"  Total Charters: {r[0]:,}")
print(f"  With Amount: {r[1]:,}")
print(f"  Total Revenue: ${r[2]:,.2f}")
print(f"  Estimated GST Collected: ${r[3]:,.2f}")

# 2. Check receipts (ITC/expense source)
print("\n2. RECEIPTS (ITC/Expense Source)")
print("-" * 80)
cur.execute("""
    SELECT COUNT(*) AS total_receipts,
           COUNT(*) FILTER (WHERE gst_amount > 0) AS with_gst,
           COALESCE(SUM(gross_amount), 0) AS total_expenses,
           COALESCE(SUM(gst_amount), 0) AS total_itcs
    FROM receipts
    WHERE receipt_date >= '2012-01-01' AND receipt_date <= '2012-12-31'
""")
r = cur.fetchone()
print(f"  Total Receipts: {r[0]:,}")
print(f"  With GST: {r[1]:,}")
print(f"  Total Expenses: ${r[2]:,.2f}")
print(f"  Total ITCs (GST Paid): ${r[3]:,.2f}")

# 3. Check driver payroll
print("\n3. DRIVER PAYROLL")
print("-" * 80)
cur.execute("""
    SELECT COUNT(*) AS total_rows,
           COUNT(DISTINCT COALESCE(employee_id::text, driver_id)) AS unique_employees,
           COUNT(*) FILTER (WHERE cpp > 0 OR ei > 0 OR tax > 0) AS with_deductions,
           COUNT(*) FILTER (WHERE cpp = 0 AND ei = 0 AND tax = 0 AND gross_pay > 0) AS missing_deductions,
           COALESCE(SUM(gross_pay), 0) AS total_gross,
           COALESCE(SUM(cpp), 0) AS total_cpp,
           COALESCE(SUM(ei), 0) AS total_ei,
           COALESCE(SUM(tax), 0) AS total_tax
    FROM driver_payroll
    WHERE year = 2012
""")
r = cur.fetchone()
print(f"  Total Payroll Rows: {r[0]:,}")
print(f"  Unique Employees: {r[1]:,}")
print(f"  With Deductions: {r[2]:,}")
print(f"  Missing Deductions: {r[3]:,} ⚠️")
print(f"  Total Gross Pay: ${r[4]:,.2f}")
print(f"  Total CPP: ${r[5]:,.2f}")
print(f"  Total EI: ${r[6]:,.2f}")
print(f"  Total Tax: ${r[7]:,.2f}")

employer_cpp = r[5]
employer_ei = Decimal(str(r[6])) * Decimal("1.4")
total_remit = r[5] + r[6] + r[7] + employer_cpp + employer_ei
print(f"  Employer CPP (match): ${employer_cpp:,.2f}")
print(f"  Employer EI (1.4x): ${employer_ei:,.2f}")
print(f"  TOTAL REMITTANCE: ${total_remit:,.2f}")

# 4. Check tax_returns
print("\n4. TAX RETURNS (Computed Results)")
print("-" * 80)
cur.execute("""
    SELECT tr.form_type, 
           tp.label,
           tr.status,
           tr.calculated_amount,
           tr.filed_amount,
           tr.filed_at
    FROM tax_returns tr
    JOIN tax_periods tp ON tr.period_id = tp.id
    WHERE tp.year = 2012
    ORDER BY tr.form_type, tp.label
""")
returns = cur.fetchall()
if returns:
    for r in returns:
        form, period, status, calc, filed, filed_at = r
        print(f"  {form.upper()} ({period})")
        print(f"    Status: {status}")
        print(f"    Calculated: ${calc:,.2f}")
        if filed:
            print(f"    Filed: ${filed:,.2f} on {filed_at}")
else:
    print("  No returns found (run compute_gst/compute_payroll --write)")

# 5. Check tax_variances
print("\n5. TAX VARIANCES (Issues Detected)")
print("-" * 80)
cur.execute("""
    SELECT tv.severity, tr.form_type, tv.field, tv.message, tv.actual, tv.expected
    FROM tax_variances tv
    JOIN tax_returns tr ON tv.tax_return_id = tr.id
    JOIN tax_periods tp ON tr.period_id = tp.id
    WHERE tp.year = 2012
    ORDER BY 
        CASE tv.severity 
            WHEN 'high' THEN 1 
            WHEN 'medium' THEN 2 
            ELSE 3 
        END,
        tr.form_type
""")
variances = cur.fetchall()
if variances:
    for v in variances:
        sev, form, field, msg, actual, expected = v
        print(f"  [{sev.upper()}] {form} - {field}")
        print(f"    {msg}")
        if actual:
            print(f"    Actual: {actual}")
        if expected:
            print(f"    Expected: {expected}")
else:
    print("  No variances detected")

# 6. Check employees table
print("\n6. EMPLOYEES (T4 Recipients)")
print("-" * 80)
cur.execute("""
    SELECT COUNT(*) AS total,
           COUNT(*) FILTER (WHERE t4_sin IS NOT NULL) AS with_sin,
           COUNT(*) FILTER (WHERE t4_sin IS NULL) AS missing_sin
    FROM employees
    WHERE employee_id IN (
        SELECT DISTINCT employee_id FROM driver_payroll WHERE year = 2012
    )
""")
r = cur.fetchone()
print(f"  Total Employees with 2012 payroll: {r[0]:,}")
print(f"  With SIN: {r[1]:,}")
print(f"  Missing SIN: {r[2]:,} {'⚠️' if r[2] > 0 else '✅'}")

# 7. Banking transactions
print("\n7. BANKING TRANSACTIONS (Verification Source)")
print("-" * 80)
cur.execute("""
    SELECT COUNT(*) AS total_transactions,
           COALESCE(SUM(credit_amount), 0) AS deposits,
           COALESCE(SUM(debit_amount), 0) AS withdrawals
    FROM banking_transactions
    WHERE transaction_date >= '2012-01-01' AND transaction_date <= '2012-12-31'
""")
r = cur.fetchone()
print(f"  Total Transactions: {r[0]:,}")
print(f"  Total Deposits: ${r[1]:,.2f}")
print(f"  Total Withdrawals: ${r[2]:,.2f}")

print("\n" + "=" * 80)
print("MISSING PROCEDURES / GAPS ANALYSIS")
print("=" * 80)

issues = []

# Check for missing T4 boxes
cur.execute("""
    SELECT COUNT(*) 
    FROM driver_payroll
    WHERE year = 2012 
      AND gross_pay > 0
      AND (t4_box_14 IS NULL OR t4_box_16 IS NULL OR t4_box_18 IS NULL OR t4_box_22 IS NULL)
""")
missing_t4_boxes = cur.fetchone()[0]
if missing_t4_boxes > 0:
    issues.append(f"Missing T4 box values in {missing_t4_boxes:,} payroll rows")

# Check for missing SINs
cur.execute("""
    SELECT COUNT(DISTINCT e.employee_id)
    FROM employees e
    JOIN driver_payroll dp ON e.employee_id = dp.employee_id
    WHERE dp.year = 2012 
      AND dp.gross_pay > 0
      AND e.t4_sin IS NULL
""")
missing_sins = cur.fetchone()[0]
if missing_sins > 0:
    issues.append(f"Missing SINs for {missing_sins} employees who were paid in 2012")

# Check for missing deductions (re-query since we lost the original result)
cur.execute("""
    SELECT COUNT(*) 
    FROM driver_payroll
    WHERE year = 2012 
      AND gross_pay > 0 
      AND (cpp = 0 OR cpp IS NULL) 
      AND (ei = 0 OR ei IS NULL) 
      AND (tax = 0 OR tax IS NULL)
""")
missing_deductions_count = cur.fetchone()[0]
if missing_deductions_count > 0:
    issues.append(f"{missing_deductions_count} payroll rows have gross pay but no CPP/EI/Tax deductions")

if issues:
    for i, issue in enumerate(issues, 1):
        print(f"{i}. ⚠️ {issue}")
else:
    print("✅ No critical data gaps detected")

print("\n" + "=" * 80)
print("RECOMMENDATIONS")
print("=" * 80)

recommendations = [
    "Run compute_gst.py --period 2012Q1..Q4 for quarterly GST returns",
    "Populate missing T4 box values (14=employment income, 16=CPP, 18=EI, 22=tax)",
    "Add missing SINs to employees table for T4 issuance",
    "Investigate 22 payroll rows with missing deductions",
    "Verify banking reconciliation for 2012 (deposits vs charter revenue)",
    "Export T4 slips individually (currently only summary CSV)",
    "Generate T4 Summary form for CRA submission",
    "Implement T2 corporate tax computation for 2012"
]

for i, rec in enumerate(recommendations, 1):
    print(f"{i}. {rec}")

conn.close()
print("\n✅ Test complete")
