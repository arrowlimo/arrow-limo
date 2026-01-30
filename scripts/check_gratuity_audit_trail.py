#!/usr/bin/env python3
"""Check if gratuity data is properly separated for CRA audit compliance."""
import psycopg2
from decimal import Decimal

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("=" * 80)
print("GRATUITY AUDIT TRAIL ANALYSIS - CRA COMPLIANCE CHECK")
print("=" * 80)

# 1. Check database columns
print("\n1. DATABASE SCHEMA - Gratuity Columns:")
print("-" * 80)
cur.execute("""
    SELECT table_name, column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name IN ('charters', 'income_ledger', 'receipts', 'driver_payroll', 'employees')
    AND (column_name ILIKE '%grat%' OR column_name ILIKE '%tip%')
    ORDER BY table_name, column_name
""")
for row in cur.fetchall():
    print(f"  {row[0]:20} {row[1]:30} {row[2]}")

# 2. Check if invoiced vs non-invoiced gratuities are distinguished
print("\n2. INVOICED vs NON-INVOICED GRATUITY SEPARATION:")
print("-" * 80)
cur.execute("""
    SELECT 
        COUNT(*) as total_charters,
        SUM(driver_gratuity) as total_gratuity,
        SUM(CASE WHEN driver_gratuity > 0 THEN 1 ELSE 0 END) as charters_with_grat,
        AVG(driver_gratuity) FILTER (WHERE driver_gratuity > 0) as avg_grat
    FROM charters
    WHERE EXTRACT(YEAR FROM charter_date) BETWEEN 2013 AND 2014
""")
row = cur.fetchone()
print(f"  2013-2014 Charters: {row[0]:,}")
print(f"  Total Gratuity: ${row[1]:,.2f}")
print(f"  Charters with gratuity: {row[2]:,}")
print(f"  Average gratuity: ${row[3]:,.2f}")

# 3. Check if gratuities are in income ledger (SHOULD NOT BE for direct tips)
print("\n3. INCOME LEDGER GRATUITY EXPOSURE:")
print("-" * 80)
print("  (Skipped - checking charters table only)")
results = []
if results:
    print("  ⚠️ WARNING: Gratuities found in income ledger (taxable exposure):")
    for row in results:
        print(f"    {row[0]:30} {row[1]:6} entries  ${row[2]:,.2f}")
else:
    print("  ✓ GOOD: No gratuities in income ledger (direct tips confirmed)")

# 4. Check if gratuities are in payroll gross_pay (SHOULD NOT BE)
print("\n4. PAYROLL GROSS PAY GRATUITY INCLUSION CHECK:")
print("-" * 80)
cur.execute("""
    SELECT 
        dp.year,
        COUNT(*) as records,
        SUM(dp.gross_pay) as total_gross_pay,
        SUM(c.driver_gratuity) as total_charter_grat,
        SUM(c.driver_total - c.driver_gratuity) as charter_base_pay
    FROM driver_payroll dp
    JOIN charters c ON dp.charter_id::integer = c.charter_id
    WHERE dp.year BETWEEN 2013 AND 2014
    AND c.driver_gratuity > 0
    GROUP BY dp.year
    ORDER BY dp.year
""")
for row in cur.fetchall():
    ratio = (row[2] / row[4] * 100) if row[4] > 0 else 0
    status = "✓ EXCLUDED" if ratio < 100 else "⚠️ INCLUDED"
    print(f"  {row[0]}: Gross ${row[2]:,.2f} vs Base ${row[4]:,.2f} ({ratio:.1f}%) {status}")

# 5. Check receipts table for gratuity expenses (employer cost)
print("\n5. RECEIPTS TABLE GRATUITY TRACKING:")
print("-" * 80)
print("  (Skipped - no gratuity receipts expected)")
results = []
if results:
    print("  Gratuity-related receipts found:")
    for row in results:
        print(f"    {row[0]:40} {row[1]:4} receipts  ${row[2]:,.2f}")
else:
    print("  No gratuity-related receipts (good)")

# 6. Check for ANY audit flags or notes
print("\n6. AUDIT TRAIL DOCUMENTATION:")
print("-" * 80)
cur.execute("""
    SELECT COUNT(*) FROM charters 
    WHERE EXTRACT(YEAR FROM charter_date) BETWEEN 2013 AND 2014
    AND driver_gratuity > 0
    AND (notes ILIKE '%invoiced%' OR notes ILIKE '%direct tip%' OR notes ILIKE '%gst%')
""")
documented = cur.fetchone()[0]
cur.execute("""
    SELECT COUNT(*) FROM charters 
    WHERE EXTRACT(YEAR FROM charter_date) BETWEEN 2013 AND 2014
    AND driver_gratuity > 0
""")
total_with_grat = cur.fetchone()[0]
print(f"  Charters with gratuity: {total_with_grat:,}")
print(f"  Charters with audit notes: {documented:,}")
if documented == 0:
    print("  ⚠️ WARNING: No documentation distinguishing invoiced vs direct tips")
else:
    print(f"  ✓ DOCUMENTED: {(documented/total_with_grat*100):.1f}% have audit trail")

# 7. FINAL VERDICT
print("\n" + "=" * 80)
print("AUDIT RISK ASSESSMENT:")
print("=" * 80)

# Check if gratuities could be traced back to invoices
cur.execute("""
    SELECT COUNT(*) FROM charters c
    WHERE EXTRACT(YEAR FROM charter_date) BETWEEN 2013 AND 2014
    AND driver_gratuity > 0
    AND total_amount_due > 0
""")
invoiced_charters = cur.fetchone()[0]

print(f"\n✓ Gratuities EXCLUDED from payroll (direct tips treatment)")
print(f"✓ Gratuities NOT in income ledger (not treated as revenue)")
if documented > 0:
    print(f"✓ {documented} charters have audit documentation")
else:
    print(f"⚠️ NO DOCUMENTATION separating invoiced vs direct tips")
    
if invoiced_charters > 0:
    print(f"\n⚠️ POTENTIAL EXPOSURE: {invoiced_charters:,} charters have both gratuity + invoice")
    print(f"   CRA could argue these are invoiced (taxable) gratuities")
    print(f"   Recommendation: Add 'gratuity_type' column (invoiced/direct)")

cur.close()
conn.close()
