#!/usr/bin/env python
"""Verify GL 9999 auto-categorization completion."""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Check GL 9999 count
cur.execute("SELECT COUNT(*) FROM receipts WHERE gl_account_code = '9999'")
count = cur.fetchone()[0]
print(f"\n{'='*80}")
print(f"GL 9999 VERIFICATION")
print(f"{'='*80}")
print(f"Remaining GL 9999 entries: {count}")

# Check all GL codes distribution
cur.execute("""
    SELECT gl_account_code, COUNT(*) as count, ROUND(SUM(COALESCE(gross_amount, 0))::numeric, 2) as total
    FROM receipts
    GROUP BY gl_account_code
    ORDER BY count DESC
""")

print("\nGL Code Distribution:")
print(f"{'Code':<10} {'Count':<10} {'Total Amount':<20}")
print("-" * 40)
total_all = 0
for row in cur.fetchall():
    code = row[0] or 'NULL'
    count_val = row[1]
    total_val = float(row[2]) if row[2] else 0
    total_all += total_val
    print(f"{code:<10} {count_val:<10} ${total_val:>18,.2f}")

cur.close()
conn.close()

print(f"\n✅ Verification complete")
