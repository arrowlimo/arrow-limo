#!/usr/bin/env python3
"""Check CLIENT FOOD and BEVERAGES GL assignment"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor()

print("\n" + "="*100)
print("CLIENT FOOD/BEVERAGES GL CODE ASSIGNMENT")
print("="*100)

cur.execute("""
    SELECT category, gl_account_code, COUNT(*) as cnt, SUM(COALESCE(gross_amount, 0)) as total
    FROM receipts
    WHERE category ILIKE '%client%food%' 
       OR category ILIKE '%client%bev%'
    GROUP BY category, gl_account_code
    ORDER BY cnt DESC
""")

rows = cur.fetchall()

if rows:
    print(f"\n{'Category':<45} {'GL Code':<10} {'Count':>5}  {'Total':>15}")
    print("="*100)
    for r in rows:
        cat = r[0]
        gl = r[1] or 'NULL'
        cnt = r[2]
        total = r[3]
        print(f"{cat:<45} {gl:<10} {cnt:>5}  ${total:>12,.2f}")
else:
    print("\n⚠️  No receipts found with CLIENT FOOD or CLIENT BEVERAGES categories")

cur.close()
conn.close()
