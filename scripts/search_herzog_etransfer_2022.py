#!/usr/bin/env python3
"""
Search for e-transfers from Herzog/Cheyenne email in 2022.
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

print('Searching for herzog/cheyenne e-transfers in 2022...\n')

# Search payments table
cur.execute('''
    SELECT payment_id, reserve_number, amount, payment_date, payment_method, notes
    FROM payments
    WHERE payment_date >= '2022-01-01' AND payment_date < '2023-01-01'
    AND (
        LOWER(notes) LIKE '%herzog%'
        OR LOWER(notes) LIKE '%cheyenne%'
        OR LOWER(notes) LIKE '%herzogcheyenne%'
        OR LOWER(reference_number) LIKE '%herzog%'
    )
    ORDER BY payment_date
''')

payments = cur.fetchall()
if payments:
    print(f'PAYMENTS TABLE: {len(payments)} matches')
    print('-' * 100)
    for p in payments:
        print(f'ID: {p[0]} | Rsv: {p[1]} | Amount: ${p[2]:,.2f} | Date: {p[3]} | Method: {p[4]}')
        print(f'  Notes: {p[5][:150] if p[5] else "(none)"}')
        print()
else:
    print('PAYMENTS TABLE: No matches found\n')

# Search banking_transactions
cur.execute('''
    SELECT transaction_id, transaction_date, description, credit_amount, debit_amount, account_number
    FROM banking_transactions
    WHERE transaction_date >= '2022-01-01' AND transaction_date < '2023-01-01'
    AND (
        LOWER(description) LIKE '%herzog%'
        OR LOWER(description) LIKE '%cheyenne%'
        OR LOWER(description) LIKE '%herzogcheyenne%'
    )
    ORDER BY transaction_date
''')

banking = cur.fetchall()
if banking:
    print(f'\nBANKING_TRANSACTIONS TABLE: {len(banking)} matches')
    print('-' * 100)
    for b in banking:
        amount = b[3] if b[3] else b[4]
        tx_type = 'CREDIT' if b[3] else 'DEBIT'
        print(f'ID: {b[0]} | Date: {b[1]} | {tx_type}: ${amount:,.2f} | Acct: {b[5]}')
        print(f'  Desc: {b[2][:150]}')
        print()
else:
    print('\nBANKING_TRANSACTIONS TABLE: No matches found')

# Search email_financial_events if exists
try:
    cur.execute('''
        SELECT id, email_date, from_email, subject, event_type, amount
        FROM email_financial_events
        WHERE email_date >= '2022-01-01' AND email_date < '2023-01-01'
        AND (
            LOWER(from_email) LIKE '%herzog%'
            OR LOWER(subject) LIKE '%herzog%'
            OR LOWER(from_email) LIKE '%cheyenne%'
            OR LOWER(subject) LIKE '%cheyenne%'
        )
        ORDER BY email_date
    ''')
    
    emails = cur.fetchall()
    if emails:
        print(f'\nEMAIL_FINANCIAL_EVENTS TABLE: {len(emails)} matches')
        print('-' * 100)
        for e in emails:
            print(f'ID: {e[0]} | Date: {e[1]} | From: {e[2]} | Type: {e[4]} | Amount: ${e[5]:,.2f}')
            print(f'  Subject: {e[3][:150]}')
            print()
    else:
        print('\nEMAIL_FINANCIAL_EVENTS TABLE: No matches found')
except Exception as ex:
    print(f'\nEMAIL_FINANCIAL_EVENTS TABLE: Error - {ex}')

cur.close()
conn.close()
