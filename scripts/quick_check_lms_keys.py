#!/usr/bin/env python3
"""Check if we have LMS payment keys already imported."""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM payments WHERE payment_key IS NOT NULL AND payment_key LIKE '00%'")
print(f'Payments with LMS Key format (00xxxxx): {cur.fetchone()[0]:,}')

cur.execute("SELECT payment_id, payment_key, account_number, reserve_number, amount, notes FROM payments WHERE payment_key LIKE '00%' LIMIT 10")
print("\nSample payments with LMS keys:")
for row in cur.fetchall():
    print(f"  Payment {row[0]}: Key={row[1]}, Account={row[2]}, Reserve={row[3]}, ${row[4]}, Notes={row[5][:50] if row[5] else ''}")

conn.close()
