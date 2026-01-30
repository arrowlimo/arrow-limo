#!/usr/bin/env python3
"""
Investigate DEPOSIT variations to understand what type they are
Round numbers vs irregular suggest CASH vs CHECK/BANKING
"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Get all DEPOSIT variations with amounts to understand patterns
cur.execute("""
    SELECT 
        r.vendor_name,
        r.gross_amount,
        r.description,
        r.receipt_date,
        COUNT(*) as cnt
    FROM receipts r
    WHERE r.vendor_name ILIKE '%deposit%'
      AND r.vendor_name NOT ILIKE '%square%'
    GROUP BY r.vendor_name, r.gross_amount, r.description, r.receipt_date
    ORDER BY r.vendor_name, r.gross_amount DESC
    LIMIT 100
""")

print("DEPOSIT VARIATIONS - AMOUNTS AND DETAILS")
print("=" * 120)
print(f"{'Vendor':<30} | {'Amount':<10} | {'Description':<60}")
print("-" * 120)

for row in cur.fetchall():
    vendor, amount, desc, date, cnt = row
    amount_str = f"${amount:>9.2f}" if amount else "NULL"
    desc_str = (desc[:58] if desc else "(no desc)")
    print(f"{vendor:<30} | {amount_str} | {desc_str}")

# Get summary of DEPOSIT types by amount patterns
print("\n\n" + "=" * 120)
print("DEPOSIT SUMMARY BY VENDOR TYPE")
print("=" * 120)

cur.execute("""
    SELECT 
        vendor_name,
        COUNT(*) as cnt,
        MIN(gross_amount) as min_amt,
        MAX(gross_amount) as max_amt,
        ROUND(AVG(gross_amount), 2) as avg_amt
    FROM receipts
    WHERE vendor_name ILIKE '%deposit%'
      AND vendor_name NOT ILIKE '%square%'
    GROUP BY vendor_name
    ORDER BY cnt DESC
""")

for row in cur.fetchall():
    vendor, cnt, min_amt, max_amt, avg_amt = row
    print(f"{cnt:>5} | {vendor:<30} | Range: ${min_amt:.2f} to ${max_amt:.2f} | Avg: ${avg_amt:.2f}")

cur.close()
conn.close()
