#!/usr/bin/env python
"""
Check if there are e-transfers for the alcohol purchase ($3,504.50 on charter 017822).
This would be the customer paying Arrow Limo for alcohol at company discount.
"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print('='*100)
print('SEARCH FOR ALCOHOL PURCHASE E-TRANSFERS')
print('='*100)

# The beverage charge is $3,504.50
beverage_charge = 3504.50
print(f'\nBeverage charge on 017822: ${beverage_charge}')
print('Looking for e-transfers around this amount in July 2023...')

# Search for e-transfers around beverage charge amount (within $100)
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE transaction_date >= '2023-07-01'
      AND transaction_date <= '2023-08-31'
      AND (description ILIKE '%transfer%' OR description ILIKE '%e-transfer%' OR description ILIKE '%interac%')
      AND ((debit_amount BETWEEN 3400 AND 3600) OR (credit_amount BETWEEN 3400 AND 3600))
    ORDER BY transaction_date
""")
transfers = cur.fetchall()

print(f'\nE-transfers $3,400-$3,600 in July-August 2023:')
if transfers:
    for t in transfers:
        amt_type = 'DEBIT' if t[3] else 'CREDIT'
        amt = t[3] if t[3] else t[4]
        print(f'  {t[1]} - {amt_type} ${amt:,.2f} - {t[2][:75]}')
else:
    print('  None found')

# Check all existing payments for 017822 to see if they match
print(f'\n{"="*100}')
print('CHARTER 017822 PAYMENT ANALYSIS')
print('='*100)

cur.execute("""
    SELECT p.payment_id, p.amount, p.payment_date, p.payment_method, p.notes
    FROM payments p
    WHERE p.reserve_number = '017822'
    ORDER BY p.payment_date
""")
payments = cur.fetchall()

print(f'\nExisting payments for 017822:')
total_paid = 0
for p in payments:
    total_paid += p[1]
    print(f'  payment_id={p[0]}: ${p[1]:,.2f} on {p[2]} via {p[3]}')
    if p[4]:
        print(f'    Notes: {p[4][:80]}')

print(f'\nTotal paid via payments table: ${total_paid:,.2f}')

# Check banking for these specific payment amounts
print(f'\n{"="*100}')
print('BANKING TRANSACTIONS FOR EXISTING PAYMENTS')
print('='*100)

for p in payments:
    print(f'\nLooking for ${p[1]:,.2f} around {p[2]}...')
    
    # Search within 7 days of payment date
    cur.execute("""
        SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE transaction_date BETWEEN %s::date - INTERVAL '7 days' AND %s::date + INTERVAL '7 days'
          AND ((ABS(debit_amount - %s) < 1.0) OR (ABS(credit_amount - %s) < 1.0))
        ORDER BY ABS(transaction_date - %s::date)
        LIMIT 5
    """, (p[2], p[2], p[1], p[1], p[2]))
    
    banking = cur.fetchall()
    if banking:
        for b in banking:
            amt_type = 'DEBIT' if b[3] else 'CREDIT'
            amt = b[3] if b[3] else b[4]
            print(f'  {b[1]} - {amt_type} ${amt:,.2f} - {b[2][:70]}')
    else:
        print(f'  No banking match found')

# Look for any credits (incoming) around $3,500 in July 2023
print(f'\n{"="*100}')
print('ALL INCOMING CREDITS $3,400-$3,600 IN JULY 2023')
print('='*100)

cur.execute("""
    SELECT transaction_id, transaction_date, description, credit_amount, balance
    FROM banking_transactions
    WHERE transaction_date >= '2023-07-01'
      AND transaction_date <= '2023-07-31'
      AND credit_amount BETWEEN 3400 AND 3600
    ORDER BY transaction_date
""")
credits = cur.fetchall()

if credits:
    for c in credits:
        print(f'  {c[1]}: +${c[3]:,.2f} - {c[2][:75]}')
else:
    print('  None found')

# Check charter 017822 charges breakdown
print(f'\n{"="*100}')
print('CHARTER 017822 CHARGES BREAKDOWN')
print('='*100)

cur.execute("""
    SELECT description, amount
    FROM charter_charges
    WHERE reserve_number = '017822'
    ORDER BY amount DESC
""")
charges = cur.fetchall()

total_charges = 0
for ch in charges:
    total_charges += ch[1]
    print(f'  ${ch[1]:>10.2f} - {ch[0]}')

print(f'  {"="*50}')
print(f'  ${total_charges:>10.2f} - TOTAL')

cur.close()
conn.close()
print('\nDone.')
