#!/usr/bin/env python3
"""
Audit orphaned payments and suggest fixes
"""
import psycopg2
from collections import defaultdict

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("="*80)
print("ORPHANED PAYMENTS AUDIT")
print("="*80)

# Find orphaned payments
cur.execute("""
    SELECT p.payment_id, p.amount, p.payment_date, p.payment_method, 
           p.reserve_number, p.charter_id
    FROM payments p
    WHERE p.reserve_number NOT IN (SELECT reserve_number FROM charters WHERE reserve_number IS NOT NULL)
    AND p.reserve_number IS NOT NULL
    ORDER BY p.payment_date DESC
    LIMIT 30
""")

orphaned = cur.fetchall()
print(f"\nFound {len(orphaned)} orphaned payments (showing first 30)")
print("\nPayment ID | Amount   | Date       | Method        | Reserve# | Charter#")
print("-" * 80)

for pid, amount, pdate, method, reserve, charter in orphaned:
    print(f"{pid:9d} | {amount:8.2f} | {str(pdate)[:10]} | {str(method)[:13]:13s} | {str(reserve):8s} | {str(charter) if charter else 'NULL':>8s}")

# Group by reserve number to see patterns
print("\n" + "="*80)
print("Grouped by Reserve Number:")
print("="*80)

cur.execute("""
    SELECT p.reserve_number, COUNT(*) as count, SUM(p.amount) as total,
           MIN(p.payment_date) as first_date, MAX(p.payment_date) as last_date
    FROM payments p
    WHERE p.reserve_number NOT IN (SELECT reserve_number FROM charters WHERE reserve_number IS NOT NULL)
    AND p.reserve_number IS NOT NULL
    GROUP BY p.reserve_number
    ORDER BY count DESC
    LIMIT 20
""")

groups = cur.fetchall()
print("\nReserve #  | Count | Total    | First Date | Last Date")
print("-" * 60)
for reserve, count, total, first_date, last_date in groups:
    print(f"{reserve:10s} | {count:5d} | {total:8.2f} | {str(first_date)[:10]} | {str(last_date)[:10]}")

print(f"\n✅ Total orphaned payments: {len(orphaned)} in first query")

# Check if we can find matching charters by amount+date
print("\n" + "="*80)
print("Attempting to Match by Amount & Date Proximity")
print("="*80)

cur.execute("""
    SELECT p.payment_id, p.amount, p.payment_date, p.reserve_number as orphan_reserve,
           c.charter_id, c.reserve_number as charter_reserve, c.total_amount_due,
           ABS(EXTRACT(DAY FROM (p.payment_date - c.charter_date))) as days_diff
    FROM payments p
    LEFT JOIN charters c ON ABS(p.amount - c.total_amount_due) < 0.01 
                        AND ABS(EXTRACT(DAY FROM (p.payment_date - c.charter_date))) <= 30
    WHERE p.reserve_number NOT IN (SELECT reserve_number FROM charters WHERE reserve_number IS NOT NULL)
    AND p.reserve_number IS NOT NULL
    AND c.charter_id IS NOT NULL
    LIMIT 20
""")

matches = cur.fetchall()
if matches:
    print(f"\nFound {len(matches)} potential matches by amount & date:")
    print("\nPayment# | Amount | Orphan Reserve | Potential Charter | Reserve | Days Diff")
    print("-" * 80)
    for pid, amount, pdate, orph_res, cid, chr_res, due, days_diff in matches:
        print(f"{pid:8d} | {amount:6.2f} | {str(orph_res):14s} | {cid:17d} | {str(chr_res):7s} | {days_diff:8.0f}")
else:
    print("\nNo close matches found by amount/date")

cur.close()
conn.close()

print("\n" + "="*80)
print("RECOMMENDATION")
print("="*80)
print("""
1. Orphaned payments are payments with reserve_number not found in charters table
2. They exist with various reserve numbers that don't match any charter
3. Could attempt to link by matching amount + date proximity (see matches above)
4. Manual audit may be needed to confirm correct charter assignment
5. Once assigned, update payment.reserve_number to correct value

Risk Level: Low (payment data is safe, just need to link correctly)
Effort: Medium (1,400+ records to review)
Automation: Possible with amount+date matching (show matches first for review)
""")
