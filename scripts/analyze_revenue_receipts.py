#!/usr/bin/env python3
"""
Analyze receipts table to find all customer payment patterns (revenue receipts).
"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Total revenue receipts
cur.execute("SELECT COUNT(*), SUM(revenue) FROM receipts WHERE revenue IS NOT NULL AND revenue > 0")
total_cnt, total_rev = cur.fetchone()
total_rev_display = f"${total_rev:,.2f}" if total_rev else "$0.00"
print(f"Total revenue receipts: {total_cnt:,}, Total revenue: {total_rev_display}")

# Revenue receipts with reserve_number
cur.execute("SELECT COUNT(*), SUM(revenue) FROM receipts WHERE revenue > 0 AND reserve_number IS NOT NULL")
with_reserve, with_reserve_amt = cur.fetchone()
with_reserve_display = f"${with_reserve_amt:,.2f}" if with_reserve_amt else "$0.00"
print(f"With reserve_number: {with_reserve:,} ({with_reserve/total_cnt*100:.1f}%), revenue: {with_reserve_display}")

# Revenue receipts with charter_id
cur.execute("SELECT COUNT(*), SUM(revenue) FROM receipts WHERE revenue > 0 AND charter_id IS NOT NULL")
with_charter, with_charter_amt = cur.fetchone()
with_charter_display = f"${with_charter_amt:,.2f}" if with_charter_amt else "$0.00"
print(f"With charter_id: {with_charter:,} ({with_charter/total_cnt*100:.1f}%), revenue: {with_charter_display}")

# Revenue receipts with employee_id
cur.execute("SELECT COUNT(*), SUM(revenue) FROM receipts WHERE revenue > 0 AND employee_id IS NOT NULL")
with_emp, with_emp_amt = cur.fetchone()
with_emp_display = f"${with_emp_amt:,.2f}" if with_emp_amt else "$0.00"
print(f"With employee_id: {with_emp:,} ({with_emp/total_cnt*100:.1f}%), revenue: {with_emp_display}")

# Revenue receipts by source_system
print("\nRevenue receipts by source_system:")
cur.execute("""
    SELECT source_system, COUNT(*), SUM(revenue)
    FROM receipts
    WHERE revenue > 0
    GROUP BY source_system
    ORDER BY SUM(revenue) DESC
""")
for ss, cnt, amt in cur.fetchall():
    print(f"  {ss or '(null)':<40} {cnt:>6,} receipts  ${amt:>14,.2f}")

# Revenue receipts by vendor pattern
print("\nRevenue receipts - Top 30 vendor_name patterns:")
cur.execute("""
    SELECT vendor_name, COUNT(*), SUM(revenue)
    FROM receipts
    WHERE revenue > 0
    GROUP BY vendor_name
    ORDER BY SUM(revenue) DESC
    LIMIT 30
""")
for vendor, cnt, amt in cur.fetchall():
    vendor_display = (vendor or '(null)')[:50]
    print(f"  {vendor_display:<52} {cnt:>5,} receipts  ${amt:>13,.2f}")

cur.close()
conn.close()
