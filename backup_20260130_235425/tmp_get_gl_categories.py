#!/usr/bin/env python
"""Get all GL categories from receipts table."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='ArrowLimousine'
)
cur = conn.cursor()

cur.execute("""
    SELECT DISTINCT category 
    FROM receipts 
    WHERE category IS NOT NULL AND category != '' 
    ORDER BY category
""")

rows = cur.fetchall()
print(f"Found {len(rows)} distinct GL categories in receipts:\n")
for r in rows:
    print(f"  \"{r[0]}\",")

cur.close()
conn.close()
