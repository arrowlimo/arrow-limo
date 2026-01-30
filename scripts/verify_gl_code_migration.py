#!/usr/bin/env python3
"""Verify GL code migration results"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata', 
    user='postgres',
    password='***REDACTED***'
)

cur = conn.cursor()

print("\n" + "="*100)
print("GL CODE DISTRIBUTION AFTER MIGRATION")
print("="*100)

cur.execute("""
    SELECT 
        gl_account_code,
        COUNT(*) as cnt,
        SUM(COALESCE(gross_amount, 0)) as total
    FROM receipts
    WHERE parent_receipt_id IS NULL
    GROUP BY gl_account_code
    ORDER BY cnt DESC
    LIMIT 20
""")

for row in cur.fetchall():
    gl = row[0] or 'NULL'
    cnt = row[1]
    total = row[2]
    print(f"{gl:<20} {cnt:>6,} receipts  ${total:>15,.2f}")

print("\n" + "="*100)
print("SUMMARY STATS")
print("="*100)

cur.execute("SELECT COUNT(*) FROM receipts WHERE gl_account_code IS NOT NULL AND gl_account_code != ''")
has_gl = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM receipts WHERE gl_account_code IS NULL OR gl_account_code = ''")
no_gl = cur.fetchone()[0]

print(f"Receipts WITH GL code: {has_gl:,}")
print(f"Receipts WITHOUT GL code: {no_gl:,}")
print(f"Coverage: {has_gl/(has_gl+no_gl)*100:.1f}%")

cur.close()
conn.close()
