#!/usr/bin/env python3
"""
Delete Scotia 2012-06-30 closing entries and find all similar month-end closings.
"""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('='*80)
print('DELETING CLOSING ENTRIES AND SCANNING FOR SIMILAR PATTERNS')
print('='*80)
print()

# Delete the three 2012-06-30 Scotia entries
cur.execute('DELETE FROM banking_transactions WHERE transaction_id IN (58817, 58818, 58819)')
deleted = cur.rowcount
print(f'✅ Deleted {deleted} Scotia 2012-06-30 closing entries')
conn.commit()
print()

# Find all month-end 'X' transactions (closing entries pattern)
print('STEP 1: Finding all month-end closing entries (description="X")')
print('-'*80)

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date) as year,
        EXTRACT(MONTH FROM transaction_date) as month,
        account_number,
        COUNT(*) as count,
        MIN(transaction_id) as first_id,
        MAX(transaction_id) as last_id
    FROM banking_transactions
    WHERE description = 'X'
    GROUP BY year, month, account_number
    ORDER BY year DESC, month DESC
""")

closing_entries = cur.fetchall()
print(f'Found {len(closing_entries)} month-end closing entry groups:')
print()

for year, month, account, count, first_id, last_id in closing_entries:
    print(f'{int(year)}-{int(month):02d} | Account {account} | {count} entries | IDs: {first_id}-{last_id}')

print()

# Get details on these entries
if closing_entries:
    print('STEP 2: Details of X-description transactions')
    print('-'*80)
    
    cur.execute("""
        SELECT transaction_id, transaction_date, account_number, debit_amount, credit_amount, balance
        FROM banking_transactions
        WHERE description = 'X'
        ORDER BY transaction_date DESC
        LIMIT 30
    """)
    
    for tid, date, acct, debit, credit, balance in cur.fetchall():
        debit_str = f'${float(debit):.2f}' if debit else '$0.00'
        credit_str = f'${float(credit):.2f}' if credit else '$0.00'
        balance_str = f'${float(balance):.2f}' if balance else 'NULL'
        print(f'{tid} | {date} | {acct} | D:{debit_str:>12} C:{credit_str:>12} | Balance: {balance_str}')

print()

# Find any other suspicious patterns (generic descriptions)
print('STEP 3: Looking for other suspicious month-end patterns')
print('-'*80)

cur.execute("""
    SELECT 
        description,
        COUNT(*) as count,
        MIN(transaction_date) as earliest,
        MAX(transaction_date) as latest
    FROM banking_transactions
    WHERE description IN ('X', 'x', 'BALANCE', 'Balance', 'balance', 'CLOSING', 'closing', '')
    GROUP BY description
    ORDER BY count DESC
""")

suspicious = cur.fetchall()
if suspicious:
    for desc, count, earliest, latest in suspicious:
        print(f'Description "{desc}": {count} entries ({earliest} to {latest})')
else:
    print('No other suspicious month-end patterns found.')

print()
print('✅ Cleanup complete')

cur.close()
conn.close()
