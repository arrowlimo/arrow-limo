#!/usr/bin/env python
"""
Search for alcohol refund e-transfer to Shaye Callin after July 27, 2023.
Amount: $1,223.15 ($1,137.25 liquor + $85.90 deposits)
"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print('='*100)
print('SEARCH FOR SHAYE CALLIN ALCOHOL REFUND')
print('='*100)
print('\nLooking for e-transfer around $1,223.15 after July 27, 2023')

# Search banking for e-transfers after July 27, 2023
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE transaction_date >= '2023-07-27'
      AND transaction_date <= '2023-09-30'
      AND (description ILIKE '%transfer%' OR description ILIKE '%e-transfer%' OR description ILIKE '%interac%')
      AND (debit_amount BETWEEN 1200 AND 1250 OR credit_amount BETWEEN 1200 AND 1250)
    ORDER BY transaction_date
""")
transfers = cur.fetchall()

print(f'\nFound {len(transfers)} transfers between $1,200-$1,250 from July 27 - Sept 30, 2023:')
for t in transfers:
    amt = t[3] if t[3] else -t[4]  # debit positive, credit negative
    print(f'  {t[1]}: ${amt:,.2f} - {t[2][:80]}')

# Broaden search - any debit around that amount
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE transaction_date >= '2023-07-27'
      AND transaction_date <= '2023-09-30'
      AND debit_amount BETWEEN 1220 AND 1225
    ORDER BY transaction_date
""")
debits = cur.fetchall()

print(f'\nAll debits $1,220-$1,225 (Jul 27 - Sept 30, 2023):')
for t in debits:
    print(f'  {t[1]}: ${t[3]:,.2f} - {t[2][:80]}')

# Check around exact amount $1,223.15
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE transaction_date >= '2023-07-27'
      AND transaction_date <= '2023-12-31'
      AND (ABS(debit_amount - 1223.15) < 1.0 OR ABS(credit_amount - 1223.15) < 1.0)
    ORDER BY transaction_date
""")
exact = cur.fetchall()

print(f'\nTransactions within $1 of $1,223.15 (Jul 27 - Dec 31, 2023):')
for t in exact:
    amt = t[3] if t[3] else -t[4]
    print(f'  {t[1]}: ${amt:,.2f} - {t[2][:80]}')

# Check for Shaye Callin charters 017822 and 017823
print(f'\n' + '='*100)
print('CHARTER 017822 & 017823 PAYMENT ANALYSIS')
print('='*100)

for reserve in ['017822', '017823']:
    cur.execute("""
        SELECT reserve_number, charter_date, total_amount_due, paid_amount, balance
        FROM charters WHERE reserve_number = %s
    """, (reserve,))
    charter = cur.fetchone()
    
    if charter:
        print(f'\n{reserve}: date={charter[1]}, total_due=${charter[2]}, paid=${charter[3]}, balance=${charter[4]}')
        
        # Get payments
        cur.execute("""
            SELECT payment_id, amount, payment_date, payment_method
            FROM payments
            WHERE reserve_number = %s
            ORDER BY payment_date
        """, (reserve,))
        payments = cur.fetchall()
        
        print(f'  Payments:')
        for p in payments:
            print(f'    {p[2]}: ${p[1]} via {p[3]} (payment_id={p[0]})')

# Search for any banking transaction with "Callin" or "Shaye" in description
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
    FROM banking_transactions
    WHERE transaction_date >= '2023-07-27'
      AND transaction_date <= '2023-12-31'
      AND (description ILIKE '%callin%' OR description ILIKE '%shaye%' OR description ILIKE '%kayla%')
    ORDER BY transaction_date
""")
name_matches = cur.fetchall()

print(f'\n' + '='*100)
print('BANKING TRANSACTIONS MENTIONING CALLIN/SHAYE/KAYLA')
print('='*100)
for t in name_matches:
    amt = t[3] if t[3] else -t[4]
    print(f'  {t[1]}: ${amt:,.2f} - {t[2][:80]}')

cur.close()
conn.close()
print('\nDone.')
