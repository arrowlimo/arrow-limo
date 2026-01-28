#!/usr/bin/env python3
"""
Check if the July 2023 Fibrenew wedding trade journal entries are captured in payments.
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
print('FIBRENEW WEDDING TRADE - JULY 2023 JOURNAL ENTRIES')
print('='*100)

# The amounts from journal entries
je21_amount = 3508.25  # Shareholders Earning
je22_amount = 2767.50  # Shareholder - wedding

print('\nJOURNAL ENTRY AMOUNTS:')
print('-'*100)
print(f'JE #21 (31/07/2023): Shareholders Earning - ${je21_amount:,.2f}')
print(f'JE #22 (31/07/2023): Shareholder - wedding - ${je22_amount:,.2f}')
print(f'Total: ${je21_amount + je22_amount:,.2f}')

# Check existing payments with "trade" or "fibrenew"
print('\n\nEXISTING TRADE PAYMENTS IN SYSTEM:')
print('-'*100)
cur.execute("""
    SELECT payment_id, reserve_number, amount, payment_date, payment_method, notes
    FROM payments
    WHERE payment_method = 'trade_of_services'
       OR LOWER(notes) LIKE '%fibrenew%'
       OR LOWER(notes) LIKE '%trade%'
    ORDER BY payment_date
""")

payments = cur.fetchall()
print(f'Found {len(payments)} trade/Fibrenew payments:')
for p in payments:
    print(f'\nPayment ID: {p[0]}')
    print(f'  Reserve: {p[1]}')
    print(f'  Amount: ${p[2]:,.2f}')
    print(f'  Date: {p[3]}')
    print(f'  Method: {p[4]}')
    print(f'  Notes: {p[5]}')

# Check the wedding charters (017822, 017823)
print('\n\n' + '='*100)
print('WEDDING CHARTERS 017822 & 017823')
print('='*100)

cur.execute("""
    SELECT reserve_number, charter_date, total_amount_due, paid_amount, balance
    FROM charters
    WHERE reserve_number IN ('017822', '017823')
    ORDER BY reserve_number
""")

charters = cur.fetchall()
for c in charters:
    print(f'\nReserve {c[0]}:')
    print(f'  Charter Date: {c[1]}')
    print(f'  Total Due: ${c[2]:,.2f}')
    print(f'  Paid: ${c[3]:,.2f}')
    print(f'  Balance: ${c[4]:,.2f}')

# Get payments for these charters
print('\n\nPAYMENTS FOR WEDDING CHARTERS:')
print('-'*100)
cur.execute("""
    SELECT reserve_number, payment_id, amount, payment_date, payment_method, notes
    FROM payments
    WHERE reserve_number IN ('017822', '017823')
    ORDER BY reserve_number, payment_date
""")

wedding_payments = cur.fetchall()
for p in wedding_payments:
    print(f'\nReserve {p[0]} - Payment ID: {p[1]}')
    print(f'  Amount: ${p[2]:,.2f}')
    print(f'  Date: {p[3]}')
    print(f'  Method: {p[4]}')
    print(f'  Notes: {p[5][:80] if p[5] else ""}')

# Check if amounts match
print('\n\n' + '='*100)
print('COMPARISON')
print('='*100)
total_wedding_payments = float(sum(p[2] for p in wedding_payments))
journal_total = je21_amount + je22_amount

print(f'Journal Entry Total: ${journal_total:,.2f}')
print(f'Wedding Payments Total: ${total_wedding_payments:,.2f}')
print(f'Difference: ${abs(journal_total - total_wedding_payments):,.2f}')

if abs(journal_total - total_wedding_payments) < 0.01:
    print('\n✓ MATCH - Journal entries already captured in payments')
else:
    print('\n⚠ MISMATCH - Need to verify amounts')
    
    # Check if there's a payment with different amount
    cur.execute("""
        SELECT payment_id, reserve_number, amount, payment_date, notes
        FROM payments
        WHERE payment_date BETWEEN '2023-07-20' AND '2023-07-31'
        AND (amount = %s OR amount = %s OR amount = %s)
    """, (je21_amount, je22_amount, journal_total))
    
    july_matches = cur.fetchall()
    if july_matches:
        print('\n\nFOUND MATCHING AMOUNTS IN JULY 2023:')
        print('-'*100)
        for p in july_matches:
            print(f'Payment ID: {p[0]} - Reserve: {p[1]} - ${p[2]:,.2f} - {p[3]}')
            print(f'  Notes: {p[4][:80] if p[4] else ""}')

cur.close()
conn.close()
