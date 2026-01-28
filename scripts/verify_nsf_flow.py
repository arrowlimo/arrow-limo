#!/usr/bin/env python3
"""
Verify NSF transaction flow on Oct 29, 2012.
Check if these are outgoing checks that bounced or incoming customer payments that bounced.
"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 120)
print("OCTOBER 29, 2012 - NSF TRANSACTION ANALYSIS")
print("=" * 120)

# Check the Oct 29 transactions - both debits and credits
cur.execute('''
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
        AND transaction_date = '2012-10-29'
    ORDER BY transaction_id
''')

print()
print(f"{'ID':<10} {'Date':<12} {'Debit':<12} {'Credit':<12} {'Balance':<12} {'Description':<50}")
print("-" * 120)

for row in cur.fetchall():
    trans_id, date, desc, debit, credit, balance = row
    debit_str = f'${debit:,.2f}' if debit else '-'
    credit_str = f'${credit:,.2f}' if credit else '-'
    balance_str = f'${balance:,.2f}' if balance else '-'
    print(f"{trans_id:<10} {str(date):<12} {debit_str:<12} {credit_str:<12} {balance_str:<12} {desc[:50]}")

print()
print("=" * 120)
print("TRANSACTIONS AROUND OCT 29 WITH NSF OR MATCHING AMOUNTS")
print("=" * 120)

# Now check broader context - days around Oct 29
cur.execute('''
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
        AND transaction_date BETWEEN '2012-10-26' AND '2012-11-01'
        AND (description ILIKE '%NSF%' OR description ILIKE '%RETURN%' 
             OR ABS(debit_amount - 1900.50) < 0.01 OR ABS(credit_amount - 1900.50) < 0.01
             OR ABS(debit_amount - 2525.25) < 0.01 OR ABS(credit_amount - 2525.25) < 0.01)
    ORDER BY transaction_date, transaction_id
''')

print()
print(f"{'ID':<10} {'Date':<12} {'Debit':<12} {'Credit':<12} {'Balance':<12} {'Description':<50}")
print("-" * 120)

for row in cur.fetchall():
    trans_id, date, desc, debit, credit, balance = row
    debit_str = f'${debit:,.2f}' if debit else '-'
    credit_str = f'${credit:,.2f}' if credit else '-'
    balance_str = f'${balance:,.2f}' if balance else '-'
    print(f"{trans_id:<10} {str(date):<12} {debit_str:<12} {credit_str:<12} {balance_str:<12} {desc[:50]}")

print()
print("=" * 120)
print("NSF FLOW INTERPRETATION")
print("=" * 120)
print("""
Scenario A: Company wrote check that bounced (our check returned NSF)
  1. Company writes check for $1900.50 (no transaction - just gives check)
  2. Check bounces - bank DEBITS $1900.50 back out (reversal)
  3. Description: "RETURNED NSF CHEQUE"
  
Scenario B: Customer paid us, their check bounced (customer check returned NSF)
  1. Customer gives us check, we deposit it - bank CREDITS $1900.50
  2. Check bounces - bank DEBITS $1900.50 (reversal)
  3. Description: "RETURNED NSF CHEQUE"

The key question: Do we see BOTH the credit AND debit?
  - If ONLY debit: Scenario A (our check bounced)
  - If credit then debit: Scenario B (customer check bounced)
""")

# Check for credits on same amounts in previous days
print("\n" + "=" * 120)
print("CHECKING FOR PRIOR DEPOSITS OF SAME AMOUNTS (Customer payment that later bounced)")
print("=" * 120)

cur.execute('''
    SELECT 
        transaction_id,
        transaction_date,
        description,
        credit_amount
    FROM banking_transactions
    WHERE account_number = '903990106011'
        AND transaction_date BETWEEN '2012-10-20' AND '2012-10-28'
        AND (ABS(credit_amount - 1900.50) < 0.01 OR ABS(credit_amount - 2525.25) < 0.01)
    ORDER BY transaction_date DESC
''')

prior_deposits = cur.fetchall()
if prior_deposits:
    print("\nFound prior deposits with matching amounts:")
    print(f"{'ID':<10} {'Date':<12} {'Credit':<12} {'Description':<60}")
    print("-" * 120)
    for trans_id, date, desc, credit in prior_deposits:
        print(f"{trans_id:<10} {str(date):<12} ${credit:>9,.2f} {desc[:60]}")
    print("\n→ This suggests customer checks that were deposited, then bounced")
else:
    print("\nNo prior deposits found with these amounts")
    print("→ This suggests company checks that bounced when presented")

cur.close()
conn.close()
