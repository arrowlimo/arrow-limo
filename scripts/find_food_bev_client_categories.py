#!/usr/bin/env python3
"""Find all food/beverage/client categories"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor()

print("\n" + "="*100)
print("ALL CATEGORIES CONTAINING: FOOD, BEVERAGE, or CLIENT")
print("="*100)

cur.execute("""
    SELECT DISTINCT category, COUNT(*) as cnt
    FROM receipts
    WHERE category ILIKE '%food%' 
       OR category ILIKE '%bev%'
       OR category ILIKE '%client%'
    GROUP BY category
    ORDER BY cnt DESC, category
""")

rows = cur.fetchall()

if rows:
    print(f"\n{'Category':<50} {'Count':>8}")
    print("="*100)
    for r in rows:
        cat = r[0]
        cnt = r[1]
        print(f"{cat:<50} {cnt:>8,}")
    print(f"\nTotal categories found: {len(rows)}")
else:
    print("\n⚠️  No categories found containing food, beverage, or client")

cur.close()
conn.close()
