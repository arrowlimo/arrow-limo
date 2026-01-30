#!/usr/bin/env python
"""Find the $500 payment for charter 019389."""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print('=== Search for 019389 payment ($500 around July 2025) ===')

# Search by account
cur.execute("""
    SELECT payment_id, reserve_number, account_number, amount, payment_date, payment_method, status
    FROM payments
    WHERE account_number = '00001'
      AND payment_date BETWEEN '2025-06-01' AND '2025-08-01'
    ORDER BY payment_date
""")
results = cur.fetchall()
print(f'\nPayments for account 00001 (Jun-Aug 2025): {len(results)}')
for r in results:
    print(f'  {r}')

# Search by reserve_number
cur.execute("""
    SELECT payment_id, reserve_number, account_number, amount, payment_date, payment_method, status
    FROM payments
    WHERE reserve_number = '019389'
    ORDER BY payment_date
""")
results2 = cur.fetchall()
print(f'\nPayments for reserve 019389: {len(results2)}')
for r in results2:
    print(f'  {r}')

# Search for ANY $500 payment around July 5, 2025
cur.execute("""
    SELECT payment_id, reserve_number, account_number, amount, payment_date, payment_method, status
    FROM payments
    WHERE ABS(amount - 500.00) < 0.01
      AND payment_date BETWEEN '2025-07-01' AND '2025-07-10'
    ORDER BY payment_date
""")
results3 = cur.fetchall()
print(f'\n$500 payments July 1-10, 2025: {len(results3)}')
for r in results3:
    print(f'  {r}')

cur.close()
conn.close()
