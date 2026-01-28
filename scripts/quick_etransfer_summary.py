#!/usr/bin/env python3
"""Quick summary of e-transfer categorization status."""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

cur.execute("""
    SELECT 
        COALESCE(category, 'NULL') as category,
        direction,
        COUNT(*) as count,
        SUM(amount) as total
    FROM etransfer_transactions
    GROUP BY category, direction
    ORDER BY category, direction
""")

print('=' * 100)
print('E-TRANSFER CATEGORIZATION STATUS')
print('=' * 100)
print(f"{'Category':<35} | {'Dir':>4} | {'Count':>6} | {'Total':>15}")
print('-' * 100)

total_count = 0
total_amount = 0.0

for cat, direction, count, amount in cur.fetchall():
    print(f"{cat:<35} | {direction:>4} | {count:>6,} | ${float(amount):>14,.2f}")
    total_count += count
    total_amount += float(amount)

print('=' * 100)
print(f"{'TOTAL':<35} | {'':>4} | {total_count:>6,} | ${total_amount:>14,.2f}")

cur.close()
conn.close()
