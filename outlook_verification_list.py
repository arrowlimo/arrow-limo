#!/usr/bin/env python3
"""Extract 41 charters needing Outlook verification"""
import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print('\n' + '='*100)
print('41 CHARTERS NEEDING OUTLOOK PAYMENT VERIFICATION')
print('='*100 + '\n')

cur.execute('''
    SELECT 
        c.reserve_number,
        ROUND(c.total_amount_due::numeric, 2),
        c.charter_date
    FROM charters c
    WHERE c.total_amount_due > 0
    AND NOT EXISTS (
        SELECT 1 FROM payments p WHERE p.reserve_number = c.reserve_number
    )
    ORDER BY c.charter_date DESC
''')

issues = cur.fetchall()
print(f'Unpaid charters (amount due but zero payments in system):\n')
print(f'{"Reserve":<12} {"Amount Due":>14} {"Date":<12}')
print('-'*45)

for reserve, amount_due, charter_date in issues:
    print(f'{reserve:<12} ${amount_due:>12,.2f}  {str(charter_date):<12}')

print()
print(f'Total: {len(issues)} charters to verify in Outlook')
print()

print('='*100)
print('NEXT STEP: Search Outlook PST for these reserve numbers to find payment records')
print('='*100 + '\n')

cur.close()
conn.close()
