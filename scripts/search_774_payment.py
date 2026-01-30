#!/usr/bin/env python3
"""
Search for $774 payment for Wright Trevor.
"""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

print('='*100)
print('SEARCHING FOR $774.00 PAYMENT')
print('='*100)

# Search payments table
cur.execute('''
    SELECT payment_id, reserve_number, amount, payment_date, payment_method, notes, reference_number
    FROM payments
    WHERE amount = 774.00
    ORDER BY payment_date DESC
''')

payments = cur.fetchall()
if payments:
    print(f'\nPAYMENTS TABLE: {len(payments)} matches')
    print('-'*100)
    for p in payments:
        print(f'Payment ID: {p[0]}')
        print(f'  Reserve: {p[1]}')
        print(f'  Amount: ${p[2]:,.2f}')
        print(f'  Date: {p[3]}')
        print(f'  Method: {p[4]}')
        print(f'  Reference: {p[6] if p[6] else "N/A"}')
        notes_text = p[5][:150] if p[5] else "N/A"
        print(f'  Notes: {notes_text}')
        print()
else:
    print('\nPAYMENTS TABLE: No $774.00 payments found')

# Search banking_transactions
cur.execute('''
    SELECT transaction_id, transaction_date, description, credit_amount, debit_amount, account_number
    FROM banking_transactions
    WHERE credit_amount = 774.00 OR debit_amount = 774.00
    ORDER BY transaction_date DESC
''')

banking = cur.fetchall()
if banking:
    print(f'\nBANKING_TRANSACTIONS TABLE: {len(banking)} matches')
    print('-'*100)
    for b in banking:
        amount = b[3] if b[3] else b[4]
        tx_type = 'CREDIT' if b[3] else 'DEBIT'
        print(f'Transaction ID: {b[0]}')
        print(f'  Date: {b[1]}')
        print(f'  {tx_type}: ${amount:,.2f}')
        print(f'  Account: {b[5]}')
        print(f'  Description: {b[2]}')
        print()
else:
    print('\nBANKING_TRANSACTIONS TABLE: No $774.00 transactions found')

# Search email_financial_events
cur.execute('''
    SELECT id, email_date, from_email, subject, event_type, amount
    FROM email_financial_events
    WHERE amount = 774.00
    ORDER BY email_date DESC
''')

emails = cur.fetchall()
if emails:
    print(f'\nEMAIL_FINANCIAL_EVENTS TABLE: {len(emails)} matches')
    print('-'*100)
    for e in emails:
        print(f'Email ID: {e[0]}')
        print(f'  Date: {e[1]}')
        print(f'  From: {e[2]}')
        print(f'  Type: {e[4]}')
        print(f'  Amount: ${e[5]:,.2f}')
        print(f'  Subject: {e[3]}')
        print()
else:
    print('\nEMAIL_FINANCIAL_EVENTS TABLE: No $774.00 events found')

# Search for Wright Trevor in charters
cur.execute('''
    SELECT charter_id, reserve_number, charter_date, client_name, total_amount_due, paid_amount, balance
    FROM charters
    WHERE LOWER(client_name) LIKE '%wright%'
    OR LOWER(client_name) LIKE '%trevor%'
    ORDER BY charter_date DESC
    LIMIT 10
''')

charters = cur.fetchall()
if charters:
    print(f'\nCHARTERS FOR WRIGHT/TREVOR: {len(charters)} matches')
    print('-'*100)
    for c in charters:
        print(f'Charter ID: {c[0]} | Reserve: {c[1]}')
        print(f'  Date: {c[2]}')
        print(f'  Client: {c[3]}')
        print(f'  Total Due: ${c[4]:,.2f}')
        print(f'  Paid: ${c[5]:,.2f}')
        print(f'  Balance: ${c[6]:,.2f}')
        print()
else:
    print('\nCHARTERS: No Wright/Trevor charters found')

# Search for reserve number 057158 specifically
cur.execute('''
    SELECT charter_id, reserve_number, charter_date, client_name, total_amount_due, paid_amount, balance
    FROM charters
    WHERE reserve_number = '057158'
''')

specific = cur.fetchone()
if specific:
    print('\nSPECIFIC CHARTER 057158 (from LMS screenshot):')
    print('-'*100)
    print(f'Charter ID: {specific[0]}')
    print(f'Reserve: {specific[1]}')
    print(f'Date: {specific[2]}')
    print(f'Client: {specific[3]}')
    print(f'Total Due: ${specific[4]:,.2f}')
    print(f'Paid: ${specific[5]:,.2f}')
    print(f'Balance: ${specific[6]:,.2f}')
else:
    print('\nCHARTER 057158: Not found in database')

cur.close()
conn.close()
