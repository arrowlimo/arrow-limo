#!/usr/bin/env python3
"""
Search for $774.00 refund for Wright Trevor reservation 017196.
"""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print('='*100)
print('SEARCHING FOR $774.00 REFUND')
print('='*100)

# Search for negative payments (refunds)
print('\n1. NEGATIVE PAYMENTS (REFUNDS):')
print('-'*100)
cur.execute('''
    SELECT payment_id, reserve_number, amount, payment_date, payment_method, notes
    FROM payments
    WHERE amount < 0
    AND ABS(amount) BETWEEN 773.99 AND 774.01
    ORDER BY payment_date DESC
''')

refunds = cur.fetchall()
if refunds:
    for r in refunds:
        print(f'Payment ID: {r[0]} | Reserve: {r[1]} | Amount: ${r[2]:,.2f} | Date: {r[3]} | Method: {r[4]}')
        print(f'  Notes: {r[5] if r[5] else "(none)"}')
        print()
else:
    print('  No negative payments found for $774.00\n')

# Search for Wright Trevor refunds of any amount
print('2. ALL REFUNDS FOR WRIGHT TREVOR (Reserve 017196):')
print('-'*100)
cur.execute('''
    SELECT payment_id, reserve_number, amount, payment_date, payment_method, notes
    FROM payments
    WHERE reserve_number = '017196'
    AND amount < 0
    ORDER BY payment_date
''')

trevor_refunds = cur.fetchall()
if trevor_refunds:
    for r in trevor_refunds:
        print(f'Payment ID: {r[0]} | Amount: ${r[2]:,.2f} | Date: {r[3]} | Method: {r[4]}')
        print(f'  Notes: {r[5] if r[5] else "(none)"}')
        print()
else:
    print('  No refunds found for reserve 017196\n')

# Search banking transactions for refund
print('3. BANKING TRANSACTIONS (DEBIT/WITHDRAWAL OF $774):')
print('-'*100)
cur.execute('''
    SELECT transaction_id, transaction_date, description, debit_amount, account_number
    FROM banking_transactions
    WHERE transaction_date >= '2022-01-01'
    AND debit_amount BETWEEN 773.99 AND 774.01
    AND (
        description ILIKE '%wright%'
        OR description ILIKE '%trevor%'
        OR description ILIKE '%refund%'
        OR description ILIKE '%e-transfer%'
    )
    ORDER BY transaction_date DESC
''')

banking = cur.fetchall()
if banking:
    for b in banking:
        print(f'TX ID: {b[0]} | Date: {b[1]} | Amount: ${b[3]:,.2f} | Account: {b[4]}')
        print(f'  Description: {b[2]}')
        print()
else:
    print('  No banking debits found for $774.00\n')

# Search for any $774 banking transactions in 2022-2023
print('4. ALL $774 BANKING TRANSACTIONS (2022-2023):')
print('-'*100)
cur.execute('''
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, account_number
    FROM banking_transactions
    WHERE transaction_date >= '2022-01-01' AND transaction_date < '2024-01-01'
    AND (
        (debit_amount BETWEEN 773.99 AND 774.01)
        OR (credit_amount BETWEEN 773.99 AND 774.01)
    )
    ORDER BY transaction_date DESC
''')

all_774 = cur.fetchall()
if all_774:
    print(f'Found {len(all_774)} transactions:')
    for b in all_774[:20]:  # Show first 20
        if b[3]:
            print(f'TX ID: {b[0]} | Date: {b[1]} | DEBIT: ${b[3]:,.2f} | Account: {b[5]}')
        else:
            print(f'TX ID: {b[0]} | Date: {b[1]} | CREDIT: ${b[4]:,.2f} | Account: {b[5]}')
        print(f'  Description: {b[2][:100]}')
        print()
    if len(all_774) > 20:
        print(f'  ... and {len(all_774)-20} more transactions')
else:
    print('  No $774 banking transactions found\n')

# Check receipts for refunds
print('5. RECEIPTS WITH NEGATIVE AMOUNTS ($774):')
print('-'*100)
cur.execute('''
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, description
    FROM receipts
    WHERE gross_amount < 0
    AND ABS(gross_amount) BETWEEN 773.99 AND 774.01
    ORDER BY receipt_date DESC
''')

receipt_refunds = cur.fetchall()
if receipt_refunds:
    for r in receipt_refunds:
        print(f'Receipt ID: {r[0]} | Date: {r[1]} | Vendor: {r[2]} | Amount: ${r[3]:,.2f}')
        print(f'  Description: {r[4] if r[4] else "(none)"}')
        print()
else:
    print('  No negative receipts found for $774.00\n')

cur.close()
conn.close()

print('='*100)
print('SUMMARY:')
print('Reserve 017196 shows -$774.00 balance (overpaid)')
print('Need to find where this overpayment went (refund issued or credit applied)')
print('='*100)
