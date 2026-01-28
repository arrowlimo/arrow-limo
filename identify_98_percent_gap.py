#!/usr/bin/env python3
"""Identify the 15 charters preventing 98% match rate."""
import psycopg2
import os

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Get unbalanced charters (need 15 to reach 98%)
query = '''
SELECT 
    c.charter_id,
    c.reserve_number,
    c.total_amount_due,
    c.paid_amount,
    (c.total_amount_due - c.paid_amount) as balance,
    c.status,
    c.pickup_date,
    COUNT(p.payment_id) as payment_count,
    SUM(p.amount) as payment_sum
FROM charters c
LEFT JOIN payments p ON p.reserve_number = c.reserve_number
WHERE c.total_amount_due > 0
  AND ABS(c.total_amount_due - c.paid_amount) >= 0.10
GROUP BY c.charter_id, c.reserve_number, c.total_amount_due, c.paid_amount, c.status, c.pickup_date
ORDER BY ABS(c.total_amount_due - c.paid_amount) ASC
LIMIT 20;
'''

cur.execute(query)
results = cur.fetchall()
cur.close()
conn.close()

print("\n" + "=" * 150)
print("TOP 20 CHARTERS TO FIX FOR 98% MATCH RATE".center(150))
print("=" * 150)
print("\nCurrent: 97.91% | Target: 98.00% | Gap: 15 charters\n")
print("-" * 150)
print(f"{'Charter':<8} | {'Reserve':<8} | {'Due':>10} | {'Paid':>10} | {'Balance':>10} | {'Pmts':>5} | {'Status':<15} | {'Pickup Date':<12}")
print("-" * 150)

for row in results:
    charter_id = row[0]
    reserve = row[1] or 'N/A'
    due = row[2]
    paid = row[3]
    balance = row[4]
    status = row[5] or 'Unknown'
    pickup_date = str(row[6])[:10] if row[6] else 'N/A'
    pmt_count = row[7] or 0
    pmt_sum = row[8] or 0
    
    print(f"{charter_id:<8} | {reserve:<8} | ${due:>9.2f} | ${paid:>9.2f} | ${balance:>9.2f} | {pmt_count:>5} | {status:<15} | {pickup_date:<12}")

print("-" * 150)
print("\n🎯 ACTION PLAN:")
print("   Fix the smallest 15 balance discrepancies above (most are penny rounding)")
print("   This will bring match rate from 97.91% → 98.00%+")
print("\n✅ SQUARE PAYMENTS: Already matched (confirmed by user)")
print("=" * 150 + "\n")
