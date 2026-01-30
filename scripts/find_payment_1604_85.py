#!/usr/bin/env python3
import psycopg2
from datetime import date

TARGET_AMOUNT = 1604.85
TARGET_DATE = date(2013, 1, 4)

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='***REDACTED***', host='localhost')
cur = conn.cursor()

print('='*80)
print(f'SEARCHING FOR PAYMENT: ${TARGET_AMOUNT} on {TARGET_DATE}')
print('='*80)

# Search payments table
print('\nPayments table:')
cur.execute("""
    SELECT payment_id, reserve_number, account_number, amount, payment_date, 
           payment_method, payment_key, status, notes
    FROM payments
    WHERE amount = %s
      AND (payment_date = %s OR payment_date::date = %s)
""", (TARGET_AMOUNT, TARGET_DATE, TARGET_DATE))

payments = cur.fetchall()
if payments:
    for p in payments:
        print(f"  Payment ID: {p[0]}")
        print(f"    Reserve: {p[1]}")
        print(f"    Account: {p[2]}")
        print(f"    Amount: ${p[3]:.2f}")
        print(f"    Date: {p[4]}")
        print(f"    Method: {p[5]}")
        print(f"    Key: {p[6]}")
        print(f"    Status: {p[7]}")
        print(f"    Notes: {p[8]}")
        print()
else:
    print("  No exact matches")

# Check for near amounts (±1.00)
print('\nNear amounts (±$1.00):')
cur.execute("""
    SELECT payment_id, reserve_number, amount, payment_date, payment_key
    FROM payments
    WHERE amount BETWEEN %s AND %s
      AND payment_date::date BETWEEN %s::date - INTERVAL '3 days' 
                                  AND %s::date + INTERVAL '3 days'
    ORDER BY ABS(amount - %s), payment_date
    LIMIT 10
""", (TARGET_AMOUNT - 1.0, TARGET_AMOUNT + 1.0, TARGET_DATE, TARGET_DATE, TARGET_AMOUNT))

near = cur.fetchall()
if near:
    for p in near:
        print(f"  ID {p[0]}: Reserve {p[1]}, ${p[2]:.2f} on {p[3]}, key={p[4]}")
else:
    print("  No near matches")

# Search banking_transactions
print('\nBanking transactions:')
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount,
           vendor_extracted, category
    FROM banking_transactions
    WHERE (debit_amount = %s OR credit_amount = %s)
      AND transaction_date = %s
""", (TARGET_AMOUNT, TARGET_AMOUNT, TARGET_DATE))

banking = cur.fetchall()
if banking:
    for b in banking:
        print(f"  Transaction ID: {b[0]}")
        print(f"    Date: {b[1]}")
        print(f"    Description: {b[2]}")
        print(f"    Debit: ${b[3]:.2f}" if b[3] else "    Debit: None")
        print(f"    Credit: ${b[4]:.2f}" if b[4] else "    Credit: None")
        print(f"    Vendor: {b[5]}")
        print(f"    Category: {b[6]}")
        print()
else:
    print("  No exact matches")
    
    # Check near amounts in banking
    print('\n  Near amounts in banking (±$1.00):')
    cur.execute("""
        SELECT transaction_id, transaction_date, description, 
               COALESCE(debit_amount, credit_amount) as amount
        FROM banking_transactions
        WHERE (debit_amount BETWEEN %s AND %s OR credit_amount BETWEEN %s AND %s)
          AND transaction_date BETWEEN %s - INTERVAL '3 days' 
                                    AND %s + INTERVAL '3 days'
        ORDER BY transaction_date
        LIMIT 10
    """, (TARGET_AMOUNT - 1.0, TARGET_AMOUNT + 1.0, TARGET_AMOUNT - 1.0, TARGET_AMOUNT + 1.0, 
          TARGET_DATE, TARGET_DATE))
    
    near_banking = cur.fetchall()
    if near_banking:
        for b in near_banking:
            print(f"    ID {b[0]}: ${b[3]:.2f} on {b[1]} - {b[2][:50]}")
    else:
        print("    No near matches")

# Search journal/GL
print('\nJournal/GL entries:')
cur.execute("""
    SELECT id, transaction_date, account_code, account_name, description, 
           debit_amount, credit_amount
    FROM unified_general_ledger
    WHERE (debit_amount = %s OR credit_amount = %s)
      AND transaction_date = %s
""", (TARGET_AMOUNT, TARGET_AMOUNT, TARGET_DATE))

gl = cur.fetchall()
if gl:
    for g in gl:
        print(f"  GL ID: {g[0]}")
        print(f"    Date: {g[1]}")
        print(f"    Account: {g[2]} - {g[3]}")
        print(f"    Description: {g[4]}")
        print(f"    Debit: ${g[5]:.2f}" if g[5] else "    Debit: None")
        print(f"    Credit: ${g[6]:.2f}" if g[6] else "    Credit: None")
        print()
else:
    print("  No matches")

cur.close()
conn.close()
