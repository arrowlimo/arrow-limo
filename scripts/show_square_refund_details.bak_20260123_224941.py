#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

cur.execute("""
    SELECT id, refund_date, amount, customer, description, square_payment_id, reference
    FROM charter_refunds
    WHERE charter_id IS NULL
    AND source_file LIKE 'items-%'
    ORDER BY amount DESC
    LIMIT 9
""")

print("Unlinked Square Refunds - ALL FIELDS:")
print("="*100)

for row in cur.fetchall():
    print(f"\nID: {row[0]}")
    print(f"  Date: {row[1]}")
    print(f"  Amount: ${row[2]:,.2f}")
    print(f"  Customer: '{row[3]}'")
    print(f"  Description: '{row[4]}'")
    print(f"  Square Payment ID: '{row[5]}'")
    print(f"  Reference: '{row[6]}'")

cur.close()
conn.close()
