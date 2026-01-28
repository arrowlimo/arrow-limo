#!/usr/bin/env python
"""Check Centratech receipts and when they were updated."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

cur.execute("""
    SELECT 
        receipt_id,
        receipt_date,
        vendor_name,
        gross_amount,
        category,
        created_at
    FROM receipts
    WHERE vendor_name ILIKE '%centratech%'
    ORDER BY receipt_date
""")

print('=' * 120)
print('CENTRATECH TECHNICAL SERVICES - Fire Extinguisher Repair')
print('=' * 120)

results = cur.fetchall()
for r in results:
    print(f'{r[0]:5d} | {r[1]} | {r[2]:40s} | ${r[3]:8.2f} | {r[4]:20s} | Created: {r[5]}')
    print()

print(f'Total: {len(results)} receipts')
print('=' * 120)

cur.close()
conn.close()
