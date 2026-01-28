#!/usr/bin/env python3
"""Move Client Entertainment from GL 6810 to GL 5900 (Charter Supplies)"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor()

print("\n" + "="*100)
print("MOVING CLIENT ENTERTAINMENT TO GL 5900 (CHARTER SUPPLIES)")
print("="*100)

# Check current state
cur.execute("""
    SELECT gl_account_code, COUNT(*) as cnt, SUM(COALESCE(gross_amount, 0)) as total
    FROM receipts
    WHERE category = 'Client Entertainment'
    GROUP BY gl_account_code
""")

print("\nCurrent state:")
for row in cur.fetchall():
    gl = row[0] or 'NULL'
    cnt = row[1]
    total = row[2]
    print(f"  GL {gl}: {cnt:,} receipts, ${total:,.2f}")

# Update to GL 5900
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5900'
    WHERE category = 'Client Entertainment'
""")

print(f"\n✅ Updated {cur.rowcount:,} receipts: Client Entertainment → GL 5900")

# Verify
cur.execute("""
    SELECT gl_account_code, COUNT(*) as cnt, SUM(COALESCE(gross_amount, 0)) as total
    FROM receipts
    WHERE category = 'Client Entertainment'
    GROUP BY gl_account_code
""")

print("\nNew state:")
for row in cur.fetchall():
    gl = row[0] or 'NULL'
    cnt = row[1]
    total = row[2]
    print(f"  GL {gl}: {cnt:,} receipts, ${total:,.2f}")

conn.commit()
print("\n✅ Changes committed")

cur.close()
conn.close()
