#!/usr/bin/env python
"""Analyze PAUL RICHARD entries to determine GL code."""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("\n" + "="*100)
print("PAUL RICHARD - GL CODE ANALYSIS")
print("="*100)

# Get PAUL RICHARD entries
cur.execute("""
    SELECT receipt_date, gross_amount, category, description, source_system, source_file
    FROM receipts
    WHERE vendor_name = 'PAUL RICHARD' AND gl_account_code = '9999'
    ORDER BY receipt_date DESC
    LIMIT 20
""")

rows = cur.fetchall()
print(f"\nFound {len(rows)} PAUL RICHARD entries\n")
print(f"{'Date':<12} {'Amount':<12} {'Category':<15} {'Description':<40} {'Source':<15}")
print("-" * 100)

for row in rows:
    date_str = row[0].isoformat() if row[0] else "N/A"
    amount = f"${float(row[1]):.2f}" if row[1] else "$0.00"
    category = (row[2] or "")[:14]
    desc = (row[3] or "")[:39]
    source = (row[4] or "")[:14]
    print(f"{date_str:<12} {amount:<12} {category:<15} {desc:<40} {source:<15}")

print("\n💡 PAUL RICHARD appears to be: DRIVER/EMPLOYEE REIMBURSEMENT")
print("   Recommended GL Code: GL 3500 (Owner/Driver Personal Draw)")
print("   OR: GL 5000 (Driver Reimbursement) if systematic")

print("\n" + "="*100)
print("NEXT GROUPS TO REVIEW (by priority)")
print("="*100)

# Get top remaining vendors
cur.execute("""
    SELECT vendor_name, COUNT(*) as count, ROUND(SUM(COALESCE(gross_amount, 0))::numeric, 2) as total
    FROM receipts
    WHERE gl_account_code = '9999'
    GROUP BY vendor_name
    ORDER BY count DESC
    LIMIT 20
""")

print(f"\n{'#':<3} {'Vendor':<50} {'Count':<8} {'Total Amount':<20}")
print("-" * 82)

vendors = cur.fetchall()
for idx, (vendor, count, total) in enumerate(vendors, 1):
    total_val = float(total) if total else 0
    print(f"{idx:<3} {vendor:<50} {count:<8} ${total_val:>18,.2f}")

cur.close()
conn.close()

print("\n✅ Next 4 priority vendors to assign GL codes:")
print("   1. [UNKNOWN POINT OF SALE] (112 entries, $35.5K) → GL 6800 or 3650?")
print("   2. CORRECTION 00339 (79 entries, $37.4K) → GL 9999 (keep for banking match)")
print("   3. PAUL RICHARD (18 entries, $8.9K) → GL 3500 (Owner Draw)")
print("   4. POINTOFSALE -VISA... (10 entries, $1.6K) → GL 3650 or 6800?")
