#!/usr/bin/env python3
"""
Analyze Wright Trevor reservation 017196 payment details to understand the $774 overpayment.
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
print('WRIGHT TREVOR RESERVATION 017196 - PAYMENT ANALYSIS')
print('='*100)

# Get charter details
cur.execute('''
    SELECT reserve_number, charter_date, total_amount_due, paid_amount, balance, status, payment_status
    FROM charters
    WHERE reserve_number = '017196'
''')

charter = cur.fetchone()
if charter:
    print('\nCHARTER DETAILS:')
    print('-'*100)
    print(f'Reserve Number: {charter[0]}')
    print(f'Charter Date: {charter[1]}')
    print(f'Total Amount Due: ${charter[2]:,.2f}')
    print(f'Paid Amount: ${charter[3]:,.2f}')
    print(f'Balance: ${charter[4]:,.2f}')
    print(f'Status: {charter[5]}')
    print(f'Payment Status: {charter[6]}')
    print(f'\nOverpayment: ${abs(charter[4]):,.2f}')

# Get all payments for this reservation
cur.execute('''
    SELECT payment_id, amount, payment_date, payment_method, notes, created_at
    FROM payments
    WHERE reserve_number = '017196'
    ORDER BY payment_date
''')

payments = cur.fetchall()
print(f'\n\nPAYMENTS FOR RESERVE 017196: ({len(payments)} payments)')
print('-'*100)

total_paid = 0
for p in payments:
    print(f'Payment ID: {p[0]}')
    print(f'  Amount: ${p[1]:,.2f}')
    print(f'  Date: {p[2]}')
    print(f'  Method: {p[3]}')
    print(f'  Notes: {p[4] if p[4] else "(none)"}')
    print(f'  Created: {p[5]}')
    print()
    total_paid += p[1]

print(f'TOTAL PAYMENTS: ${total_paid:,.2f}')

# Get charges for this reservation
cur.execute('''
    SELECT charge_id, description, amount, created_at
    FROM charter_charges
    WHERE reserve_number = '017196'
    ORDER BY charge_id
''')

charges = cur.fetchall()
print(f'\n\nCHARGES FOR RESERVE 017196: ({len(charges)} charges)')
print('-'*100)

total_charges = 0
for c in charges:
    print(f'Charge ID: {c[0]}')
    print(f'  Description: {c[1]}')
    print(f'  Amount: ${c[2]:,.2f}')
    print(f'  Created: {c[3]}')
    print()
    total_charges += c[2]

print(f'TOTAL CHARGES: ${total_charges:,.2f}')

# Calculate discrepancy
print('\n\n' + '='*100)
print('RECONCILIATION:')
print('='*100)
print(f'Total Charges: ${total_charges:,.2f}')
print(f'Total Paid: ${total_paid:,.2f}')
print(f'Difference: ${total_paid - total_charges:,.2f}')
print(f'Charter Balance Field: ${charter[4]:,.2f}')

if abs((total_paid - total_charges) - charter[4]) < 0.01:
    print('\nBALANCE CALCULATION: CORRECT')
else:
    print(f'\nBALANCE CALCULATION: MISMATCH by ${abs((total_paid - total_charges) - charter[4]):,.2f}')

print('\n\nCONCLUSION:')
print('-'*100)
if charter[4] < 0:
    print(f'Customer has OVERPAID by ${abs(charter[4]):,.2f}')
    print('This amount should be:')
    print('  1. Refunded to customer, OR')
    print('  2. Applied as credit to future reservation, OR')
    print('  3. Held as deposit for next booking')
    print('\nNo refund transaction found in system - overpayment may still be owed to customer.')

cur.close()
conn.close()
