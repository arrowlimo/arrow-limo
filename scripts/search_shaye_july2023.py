#!/usr/bin/env python
"""
Search for transactions around July 2023 (Callin Shaye charter dates) for $1,223.15 refund.
"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('='*100)
print('SEARCH AROUND JULY 2023 FOR SHAYE REFUND')
print('='*100)

# All transactions in July-August 2023 between $1,200-$1,250
print('\n1. All transactions Jul-Aug 2023 between $1,200-$1,250:')
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, 
           balance, vendor_extracted, category
    FROM banking_transactions
    WHERE transaction_date BETWEEN '2023-07-01' AND '2023-08-31'
      AND ((debit_amount BETWEEN 1200 AND 1250) OR (credit_amount BETWEEN 1200 AND 1250))
    ORDER BY transaction_date
""")
july_aug = cur.fetchall()

print(f'   Found {len(july_aug)} transactions:')
for t in july_aug:
    debit = f'-${t[3]}' if t[3] else ''
    credit = f'+${t[4]}' if t[4] else ''
    amount = debit or credit
    print(f'   {t[1]} - {amount:<13} - {t[2][:75]}')

# Check payments for charters 017822 and 017823
print('\n2. Payments for charters 017822 and 017823:')
cur.execute("""
    SELECT p.payment_id, p.reserve_number, p.amount, p.payment_date, p.payment_method,
           p.notes
    FROM payments p
    WHERE p.reserve_number IN ('017822', '017823')
    ORDER BY p.payment_date
""")
payments = cur.fetchall()

print(f'   Found {len(payments)} payments:')
for p in payments:
    print(f'   payment_id={p[0]}: reserve={p[1]}, ${p[2]} on {p[3]} via {p[4]}')
    if p[5]:
        print(f'      Notes: {p[5][:80]}')

# Check charter_charges for these charters
print('\n3. Charges for charters 017822 and 017823:')
cur.execute("""
    SELECT charge_id, reserve_number, description, amount, charge_date
    FROM charter_charges
    WHERE reserve_number IN ('017822', '017823')
    ORDER BY reserve_number, charge_date
""")
charges = cur.fetchall()

print(f'   Found {len(charges)} charges:')
total_017822 = 0
total_017823 = 0
for ch in charges:
    print(f'   {ch[1]}: {ch[2][:50]} - ${ch[3]}')
    if ch[1] == '017822':
        total_017822 += ch[3]
    else:
        total_017823 += ch[3]

print(f'\n   017822 total charges: ${total_017822}')
print(f'   017823 total charges: ${total_017823}')

# Look for any transaction with "017822" or "017823" in description
print('\n4. Banking transactions mentioning charter numbers:')
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
    FROM banking_transactions
    WHERE description ILIKE '%017822%' OR description ILIKE '%017823%'
    ORDER BY transaction_date
""")
charter_refs = cur.fetchall()

if charter_refs:
    print(f'   Found {len(charter_refs)} transactions:')
    for t in charter_refs:
        amount = f'-${t[3]}' if t[3] else f'+${t[4]}'
        print(f'   {t[1]} - {amount} - {t[2]}')
else:
    print('   No banking transactions reference these charter numbers')

# Check if there are any refund-related charges
print('\n5. Charges with "refund" or "alcohol" in description:')
cur.execute("""
    SELECT charge_id, reserve_number, description, amount, charge_date
    FROM charter_charges
    WHERE reserve_number IN ('017822', '017823')
      AND (description ILIKE '%refund%' OR description ILIKE '%alcohol%' 
           OR description ILIKE '%beverage%' OR description ILIKE '%drink%')
""")
refund_charges = cur.fetchall()

if refund_charges:
    print(f'   Found {len(refund_charges)} charges:')
    for ch in refund_charges:
        print(f'   {ch[1]}: {ch[2]} - ${ch[3]}')
else:
    print('   No refund/alcohol charges found')

cur.close()
conn.close()
print('\nDone.')
