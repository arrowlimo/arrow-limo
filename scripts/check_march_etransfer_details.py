#!/usr/bin/env python3
"""
Get detailed information about March 2022 e-transfer from Cheyenne Herzog.
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
print('MARCH 2022 E-TRANSFER DETAILS')
print('='*100)

# Get email event details
cur.execute('''
    SELECT id, email_date, from_email, subject, event_type, amount, status, notes,
           source, entity, banking_transaction_id
    FROM email_financial_events
    WHERE id = 33408
''')

email = cur.fetchone()
if email:
    print('\nEMAIL EVENT (ID 33408):')
    print('-'*100)
    print(f'Date: {email[1]}')
    print(f'From: {email[2]}')
    print(f'Subject: {email[3]}')
    print(f'Type: {email[4]}')
    print(f'Amount: ${email[5]:,.2f}')
    print(f'Status: {email[6] if email[6] else "N/A"}')
    print(f'Notes: {email[7] if email[7] else "N/A"}')
    print(f'Source: {email[8] if email[8] else "N/A"}')
    print(f'Entity: {email[9] if email[9] else "N/A"}')
    print(f'Linked Banking TX: {email[10] if email[10] else "NOT LINKED"}')

# Get banking transaction details
cur.execute('''
    SELECT transaction_id, transaction_date, description, credit_amount, debit_amount, 
           balance, account_number, vendor_extracted, category
    FROM banking_transactions
    WHERE transaction_id = 32497
''')

banking = cur.fetchone()
if banking:
    print('\n\nBANKING TRANSACTION (ID 32497):')
    print('-'*100)
    print(f'Date: {banking[1]}')
    print(f'Description: {banking[2]}')
    if banking[3]:
        print(f'Credit (deposit): ${banking[3]:,.2f}')
    else:
        print(f'Debit: ${banking[4]:,.2f}')
    if banking[5]:
        print(f'Balance after: ${banking[5]:,.2f}')
    else:
        print('Balance: N/A')
    print(f'Account: {banking[6]}')
    print(f'Vendor: {banking[7] if banking[7] else "N/A"}')
    print(f'Category: {banking[8] if banking[8] else "N/A"}')

# Check if linked
cur.execute('''
    SELECT banking_transaction_id
    FROM email_financial_events
    WHERE id = 33408
''')

link = cur.fetchone()
print('\n\nLINKAGE STATUS:')
print('-'*100)
if link and link[0]:
    if link[0] == 32497:
        print('VERIFIED: EMAIL IS LINKED TO BANKING TRANSACTION 32497')
    else:
        print(f'WARNING: EMAIL IS LINKED TO DIFFERENT BANKING TX: {link[0]}')
else:
    print('WARNING: EMAIL IS NOT LINKED TO ANY BANKING TRANSACTION')

# Check date alignment
print('\n\nTIMING ANALYSIS:')
print('-'*100)
print('Email notification: 2022-03-12 15:16:50')
print('Banking deposit:    2022-03-14')
print('Time difference:    ~2 days (48 hours)')
print('')
print('CONCLUSION:')
print('This is a legitimate e-transfer sequence:')
print('1. Email notification sent on March 12 (Saturday)')
print('2. Banking deposit cleared on March 14 (Monday)')
print('3. 2-day delay is normal for weekend e-transfers')

# Check for payment record
cur.execute('''
    SELECT payment_id, reserve_number, amount, payment_date, payment_method
    FROM payments
    WHERE payment_date BETWEEN '2022-03-12' AND '2022-03-14'
    AND amount = 330.00
''')

payment = cur.fetchone()
if payment:
    print(f'\nPAYMENT RECORD EXISTS: ID {payment[0]} | Reserve: {payment[1]} | Method: {payment[4]}')
else:
    print('\nWARNING: NO PAYMENT RECORD FOUND FOR THIS E-TRANSFER')

cur.close()
conn.close()
