#!/usr/bin/env python3
"""Quick check of email_financial_events amounts"""
import os, psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()
cur.execute("""
    SELECT event_type, COUNT(*), SUM(amount) 
    FROM email_financial_events 
    WHERE amount > 0 
    GROUP BY event_type 
    ORDER BY SUM(amount) DESC
""")
print('Email Financial Events Breakdown:')
print(f"{'Event Type':<30s} | {'Count':>6s} | {'Total Amount':>15s}")
print('-' * 60)
for r in cur.fetchall():
    print(f'{r[0]:<30s} | {r[1]:6,} | ${r[2]:14,.2f}')

# Check for anomalies
cur.execute("""
    SELECT event_type, amount, subject, email_date
    FROM email_financial_events 
    WHERE amount > 1000000
    ORDER BY amount DESC
    LIMIT 10
""")
print('\nLarge amounts (>$1M):')
for r in cur.fetchall():
    print(f'  {r[0]}: ${r[1]:,.2f} - {r[2][:50]} ({r[3]})')

cur.close()
conn.close()
