#!/usr/bin/env python3
"""Check charter 019209 details."""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

conn = get_db_connection()
cur = conn.cursor()

# Check charter 019209
cur.execute("""
    SELECT reserve_number, charter_date, client_name, 
           total_amount_due, paid_amount, balance,
           rate, deposit
    FROM charters 
    WHERE reserve_number = '019209'
""")
charter = cur.fetchone()

if charter:
    print('Charter 019209:')
    print(f'  Reserve: {charter[0]}')
    print(f'  Date: {charter[1]}')
    print(f'  Client: {charter[2]}')
    print(f'  Total Due: ${charter[3]}')
    print(f'  Paid: ${charter[4]}')
    print(f'  Balance: ${charter[5]}')
    print(f'  Rate: ${charter[6]}')
    print(f'  Deposit: ${charter[7]}')
    
    # Check charges
    print(f'\nCharges:')
    cur.execute("""
        SELECT description, amount 
        FROM charter_charges 
        WHERE charter_id = (SELECT charter_id FROM charters WHERE reserve_number = '019209')
    """)
    charges = cur.fetchall()
    if charges:
        total_charges = 0
        for desc, amt in charges:
            print(f'  {desc}: ${amt}')
            total_charges += float(amt)
        print(f'  TOTAL CHARGES: ${total_charges}')
    else:
        print('  No charges found')
    
    # Check payments
    print(f'\nPayments:')
    cur.execute("""
        SELECT payment_date, amount, payment_method
        FROM payments 
        WHERE reserve_number = '019209'
        ORDER BY payment_date
    """)
    payments = cur.fetchall()
    if payments:
        total_paid = 0
        for pdate, amt, method in payments:
            print(f'  {pdate}: ${amt} ({method})')
            total_paid += float(amt)
        print(f'  TOTAL PAID: ${total_paid}')
    else:
        print('  No payments found')
        
    print(f'\nLMS Screenshot shows:')
    print(f'  Service Fee P5: 1708.00 + 1780.00 = 3488.00')
    print(f'  Mileage In 0: -8.00 + -8.00 = -16.00')
    print(f'  Gratuity Pct: -339.00 + 321.00 = -18.00')
    print(f'  G.S.T. Pst: 5.00 + 84.62 = 89.62')
    print(f'  TOTAL: 2,410.00 + 2,210.00 = 4,620.00 (but shows as 3543.62 in charges)')
    
else:
    print('Charter 019209 not found')

cur.close()
conn.close()
