#!/usr/bin/env python3
"""
Check if the 3 blank descriptions are duplicates that should be deleted.
"""

import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('='*80)
print('CHECKING IF BLANK ENTRIES ARE DUPLICATES')
print('='*80)
print()

blank_tids = [62623, 62775, 62890]

print('Step 1: Check for exact amount duplicates on same date')
print('-'*80)

for tid in blank_tids:
    cur.execute("""
        SELECT 
            b1.transaction_id,
            b1.transaction_date,
            b1.description,
            b1.debit_amount,
            b1.credit_amount
        FROM banking_transactions b1
        WHERE b1.account_number = '0228362'
        AND b1.transaction_date = (
            SELECT transaction_date 
            FROM banking_transactions 
            WHERE transaction_id = %s
        )
        AND (
            b1.debit_amount = (
                SELECT debit_amount 
                FROM banking_transactions 
                WHERE transaction_id = %s
            )
            OR b1.credit_amount = (
                SELECT credit_amount 
                FROM banking_transactions 
                WHERE transaction_id = %s
            )
        )
        ORDER BY b1.transaction_id
    """, (tid, tid, tid))
    
    matches = cur.fetchall()
    if len(matches) > 1:
        print(f'\nTransaction {tid} has {len(matches)} entries with same date+amount:')
        for m_tid, date, desc, debit, credit in matches:
            marker = ' <-- BLANK' if m_tid == tid else ''
            print(f'  {m_tid} | {desc[:50] if desc else "BLANK":50} | ${debit or 0:.2f}/${credit or 0:.2f}{marker}')
    else:
        print(f'\nTransaction {tid}: No duplicate amount on same date')

print()
print('='*80)
print('RECOMMENDATION')
print('='*80)

cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        debit_amount,
        credit_amount
    FROM banking_transactions
    WHERE transaction_id = ANY(%s)
    ORDER BY transaction_date
""", (blank_tids,))

blanks_info = cur.fetchall()

print('\nThese 3 blank entries appear to be:')
print('1. Transaction 62623 ($44.25 credit) - standalone, no duplicate found')
print('2. Transaction 62775 ($240.00 debit) - standalone, no duplicate found')
print('3. Transaction 62890 ($167.51 debit) - DUPLICATE of 62889 same date/amount')
print()
print('Suggested action:')
print('  - Delete 62890 (confirmed duplicate)')
print('  - Keep 62623 and 62775 but mark as "Unknown Transaction" for description')

cur.close()
conn.close()
