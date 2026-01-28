#!/usr/bin/env python3
"""Final determination: Are CHQ 25-28, 33 outstanding or duplicates?"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print('=' * 120)
print('FINAL ANALYSIS: CHQ 25, 26, 27, 28 ($1475.25) AND CHQ 33 ($2525.25)')
print('=' * 120)

# Get all existing HEFFNER $1475.25 matches
cur.execute('''
    SELECT cheque_number, cheque_date, amount, banking_transaction_id
    FROM cheque_register
    WHERE payee ILIKE '%HEFFNER%'
      AND amount = 1475.25
      AND banking_transaction_id IS NOT NULL
    ORDER BY cheque_number::INTEGER
''')

print('\nExisting CHQ records with $1475.25 HEFFNER AUTO (already matched):')
print('-' * 120)
matched_1475 = cur.fetchall()
for chq, date, amount, tx_id in matched_1475:
    print(f'  CHQ {chq:3s} ({date}): TX {tx_id}')

print(f'Total: {len(matched_1475)} cheques')

# Get all banking HEFFNER $1475.25 transactions in 2012
cur.execute('''
    SELECT transaction_id, transaction_date, debit_amount, credit_amount, description
    FROM banking_transactions
    WHERE (description ILIKE '%HEFFNER%' OR description ILIKE '%Cheque Expense%')
      AND (debit_amount = 1475.25 OR credit_amount = 1475.25)
      AND transaction_date >= '2012-09-01'
      AND transaction_date <= '2012-12-31'
    ORDER BY transaction_date
''')

print('\n\nAll Banking transactions with $1475.25 in SEPT-DEC 2012:')
print('-' * 120)
bank_1475 = cur.fetchall()
for tx_id, tx_date, debit, credit, desc in bank_1475:
    amount = debit or credit
    tx_type = 'DEBIT' if debit else 'CREDIT'
    print(f'  TX {tx_id:6d} ({tx_date}): {tx_type:6s} {float(amount):10.2f}  {desc[:70]}')

print(f'Total: {len(bank_1475)} transactions')

print('\n' + '=' * 120)
print('SUMMARY FOR $1475.25:')
print('=' * 120)
print(f'CHQ 23: $1475.25 HEFFNER AUTO (2012-09-25) → TX 69370 ✓')
print(f'CHQ 24: $1475.25 HEFFNER AUTO (2013-04-29) → TX 78251 ✓')
print(f'\nMissing CHQs: 25, 26, 27, 28 (all $1475.25, NO DATES)')
print(f'Banking has {len(bank_1475)} total $1475.25 transactions')
print(f'\nConclusion: Cannot uniquely match CHQ 25, 26, 27, 28 WITHOUT dates.')
print(f'These could be:')
print(f'  1. Outstanding cheques (never deposited)')
print(f'  2. Duplicate entries (already deposited as different CHQ)')
print(f'  3. Cancelled/voided cheques')

# Now check 2525.25
cur.execute('''
    SELECT cheque_number, cheque_date, amount, banking_transaction_id
    FROM cheque_register
    WHERE payee ILIKE '%HEFFNER%'
      AND amount = 2525.25
      AND banking_transaction_id IS NOT NULL
    ORDER BY cheque_number::INTEGER
''')

print('\n\n' + '=' * 120)
print('MATCHING ANALYSIS FOR $2525.25:')
print('=' * 120)

print('\nExisting CHQ records with $2525.25 HEFFNER AUTO (already matched):')
print('-' * 120)
matched_2525 = cur.fetchall()
for chq, date, amount, tx_id in matched_2525:
    print(f'  CHQ {chq:3s} ({date}): TX {tx_id}')

print(f'Total: {len(matched_2525)} cheques')

cur.execute('''
    SELECT transaction_id, transaction_date, debit_amount, credit_amount, description
    FROM banking_transactions
    WHERE (description ILIKE '%HEFFNER%' OR description ILIKE '%Cheque Expense%')
      AND (debit_amount = 2525.25 OR credit_amount = 2525.25)
      AND transaction_date >= '2012-09-01'
      AND transaction_date <= '2012-12-31'
    ORDER BY transaction_date
''')

print('\n\nAll Banking transactions with $2525.25 in SEPT-DEC 2012:')
print('-' * 120)
bank_2525 = cur.fetchall()
for tx_id, tx_date, debit, credit, desc in bank_2525:
    amount = debit or credit
    tx_type = 'DEBIT' if debit else 'CREDIT'
    print(f'  TX {tx_id:6d} ({tx_date}): {tx_type:6s} {float(amount):10.2f}  {desc[:70]}')

print(f'Total: {len(bank_2525)} transactions')

print('\n' + '=' * 120)
print('SUMMARY FOR $2525.25:')
print('=' * 120)
for chq, date, amount, tx_id in matched_2525:
    print(f'CHQ {chq}: $2525.25 HEFFNER AUTO ({date}) → TX {tx_id} ✓')

print(f'\nMissing CHQ: 33 ($2525.25, NO DATE)')
print(f'Banking has {len(bank_2525)} total $2525.25 transactions')
print(f'\nConclusion: Cannot uniquely match CHQ 33 WITHOUT a date.')

# Final summary
print('\n\n' + '=' * 120)
print('FINAL CONCLUSION:')
print('=' * 120)
print(f'\nCHQ 25, 26, 27, 28 ($1475.25): 4 outstanding/unmatched cheques')
print(f'CHQ 33 ($2525.25): 1 outstanding/unmatched cheque')
print(f'\nThese 5 cheques lack dates and cannot be safely matched to banking records.')
print(f'Recommend marking as "OUTSTANDING" status in database.')

cur.close()
conn.close()
