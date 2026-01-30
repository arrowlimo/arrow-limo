#!/usr/bin/env python3
"""Review high-value uncategorized receipts for manual categorization."""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("="*120)
print("HIGH-VALUE UNCATEGORIZED RECEIPTS (>$1,000)")
print("="*120)

cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, description
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND gross_amount > 1000
    ORDER BY gross_amount DESC
    LIMIT 50
""")

rows = cur.fetchall()
print(f"\n{'ID':8s} | Date       | {'Vendor':28s} | Amount     | Description")
print("-"*120)
for r in rows:
    vendor = (r[2] or "")[:28]
    desc = (r[4] or "")[:50]
    print(f"{r[0]:8d} | {r[1]} | {vendor:28s} | ${r[3]:>9.2f} | {desc}")

cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND gross_amount > 1000
""")
total_count, total_amount = cur.fetchone()

print("-"*120)
print(f"Total: {total_count} receipts worth ${total_amount:,.2f}")

# Show breakdown by vendor for high-value
print("\n" + "="*120)
print("HIGH-VALUE BY VENDOR")
print("="*120)
cur.execute("""
    SELECT vendor_name, COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND gross_amount > 1000
    GROUP BY vendor_name
    ORDER BY SUM(gross_amount) DESC
    LIMIT 20
""")

print(f"{'Vendor':40s} | Count | Total Amount")
print("-"*120)
for vendor, count, amount in cur.fetchall():
    print(f"{(vendor or 'Unknown')[:38]:38s} | {count:5d} | ${amount:>12,.2f}")

conn.close()
