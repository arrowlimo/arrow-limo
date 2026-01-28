#!/usr/bin/env python3
"""
Extract 41 charters needing Outlook verification
These have amount_due but zero payment records
"""

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
print('CHARTER-PAYMENT VERIFICATION: 41 CHARTERS FOR OUTLOOK VERIFICATION')
print('='*100 + '\n')

# Key finding: 41 charters with unpaid status - these need Outlook verification
cur.execute('''
    SELECT 
        c.charter_id,
        c.reserve_number,
        ROUND(c.total_amount_due::numeric, 2) as amount_due,
        c.charter_date,
        c.charter_customer_name
    FROM charters c
    WHERE c.total_amount_due > 0
    AND NOT EXISTS (
        SELECT 1 FROM payments p WHERE p.reserve_number = c.reserve_number
    )
    ORDER BY c.charter_date DESC
    LIMIT 41
''')

issues = cur.fetchall()
print(f'41 Charters with ZERO payment records - need Outlook verification:\n')
print(f'{"Reserve":<10} {"Amount":>12} {"Customer":<25} {"Date":<12}')
print('-'*80)

for cid, reserve, amount_due, charter_date, customer in issues:
    cust_str = (str(customer) if customer else 'UNKNOWN')[:23]
    print(f'{reserve:<10} ${amount_due:>10,.2f}  {cust_str:<25} {str(charter_date):<12}')

print()
print('='*100)
print('ACTION: Compare these 41 reserves against Outlook PST for matching payment emails/receipts')
print('='*100 + '\n')

cur.close()
conn.close()
