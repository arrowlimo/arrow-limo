#!/usr/bin/env python3
"""
Check original descriptions for the 3 remaining blank entries.
"""

import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print('='*80)
print('CHECKING ORIGINAL DATA FOR 3 BLANK DESCRIPTIONS')
print('='*80)
print()

blank_tids = [62623, 62775, 62890]

print('Step 1: Check if these exist in backup tables')
print('-'*80)

# Check recent backups
backup_tables = [
    'banking_transactions_cibc_x_backup_20251206_213310',
    'banking_transactions_qb_backup_20251206_213435'
]

for table in backup_tables:
    try:
        cur.execute(f"""
            SELECT transaction_id, description, debit_amount, credit_amount
            FROM {table}
            WHERE transaction_id = ANY(%s)
        """, (blank_tids,))
        
        results = cur.fetchall()
        if results:
            print(f'\nFound in {table}:')
            for tid, desc, debit, credit in results:
                print(f'  {tid} | {desc} | ${debit or 0:.2f}/${credit or 0:.2f}')
    except:
        pass

print()
print('Step 2: Check current banking_transactions for context')
print('-'*80)

cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance
    FROM banking_transactions
    WHERE transaction_id = ANY(%s)
    ORDER BY transaction_date
""", (blank_tids,))

print('Current state:')
for tid, date, desc, debit, credit, bal in cur.fetchall():
    print(f'{tid} | {date} | "{desc}" | D:${debit or 0:.2f} C:${credit or 0:.2f} | Bal:${bal or 0:.2f}')

print()
print('Step 3: Check nearby transactions for context')
print('-'*80)

for tid in blank_tids:
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount
        FROM banking_transactions
        WHERE account_number = '0228362'
        AND transaction_id BETWEEN %s - 5 AND %s + 5
        ORDER BY transaction_id
    """, (tid, tid))
    
    print(f'\nAround transaction {tid}:')
    for t_id, date, desc, debit, credit in cur.fetchall():
        marker = ' <-- BLANK' if t_id == tid else ''
        print(f'  {t_id} | {date} | {desc[:50] if desc else "BLANK"} | ${debit or 0:.2f}/${credit or 0:.2f}{marker}')

cur.close()
conn.close()
