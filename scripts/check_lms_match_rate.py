#!/usr/bin/env python3
"""Check LMS payment matching status."""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM payments WHERE payment_key LIKE '00%' AND charter_id IS NOT NULL")
matched = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM payments WHERE payment_key LIKE '00%' AND charter_id IS NULL")
unmatched = cur.fetchone()[0]

print(f'LMS payments (with 00xxxxx keys):')
print(f'  Matched: {matched:,}')
print(f'  Unmatched: {unmatched:,}')
print(f'  Match rate: {100*matched/(matched+unmatched):.1f}%')

conn.close()
