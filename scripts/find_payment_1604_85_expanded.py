#!/usr/bin/env python3
import psycopg2

TARGET_AMOUNT = 1604.85

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='***REMOVED***', host='localhost')
cur = conn.cursor()

print('='*80)
print(f'EXPANDED SEARCH FOR AMOUNT: ${TARGET_AMOUNT} (any date in 2013)')
print('='*80)

# Payments in 2013
print('\nPayments table (2013):')
cur.execute("""
    SELECT payment_id, reserve_number, amount, payment_date, payment_key, notes
    FROM payments
    WHERE amount = %s
      AND EXTRACT(YEAR FROM payment_date) = 2013
    ORDER BY payment_date
""", (TARGET_AMOUNT,))

payments = cur.fetchall()
if payments:
    for p in payments:
        print(f"  ID {p[0]}: Reserve {p[1]}, ${p[2]:.2f} on {p[3]}, key={p[4]}")
        if p[5]:
            print(f"    Notes: {p[5]}")
else:
    print("  No matches in 2013")

# Check all years for this amount
print(f'\nAll occurrences of ${TARGET_AMOUNT} in payments (any year):')
cur.execute("""
    SELECT payment_id, reserve_number, amount, payment_date, payment_key
    FROM payments
    WHERE amount = %s
    ORDER BY payment_date
""", (TARGET_AMOUNT,))

all_payments = cur.fetchall()
if all_payments:
    for p in all_payments:
        print(f"  ID {p[0]}: Reserve {p[1]}, ${p[2]:.2f} on {p[3]}, key={p[4]}")
else:
    print("  No matches")

# Banking 2013
print('\nBanking transactions (2013):')
cur.execute("""
    SELECT transaction_id, transaction_date, description, 
           COALESCE(debit_amount, 0) as debit, COALESCE(credit_amount, 0) as credit
    FROM banking_transactions
    WHERE (debit_amount = %s OR credit_amount = %s)
      AND EXTRACT(YEAR FROM transaction_date) = 2013
    ORDER BY transaction_date
""", (TARGET_AMOUNT, TARGET_AMOUNT))

banking = cur.fetchall()
if banking:
    for b in banking:
        amt_type = 'debit' if b[3] > 0 else 'credit'
        print(f"  ID {b[0]}: ${b[3] if b[3] > 0 else b[4]:.2f} {amt_type} on {b[1]}")
        print(f"    {b[2]}")
else:
    print("  No matches")

# Check LMS directly
print('\nChecking LMS Payment table:')
import pyodbc
LMS_PATH = r'L:\New folder\lms.mdb'
try:
    lms_conn = pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};')
    lms_cur = lms_conn.cursor()
    
    lms_cur.execute("""
        SELECT PaymentID, Account_No, Reserve_No, Amount, [Key], LastUpdated
        FROM Payment
        WHERE Amount = ?
          AND LastUpdated >= #2013-01-01# AND LastUpdated < #2014-01-01#
        ORDER BY LastUpdated
    """, (TARGET_AMOUNT,))
    
    lms_rows = lms_cur.fetchall()
    if lms_rows:
        for r in lms_rows:
            print(f"  LMS Payment {r[0]}: Reserve {r[2]}, Account {r[1]}, ${r[3]:.2f}")
            print(f"    Date: {r[5]}, Key: {r[4]}")
    else:
        print("  No matches in LMS 2013")
    
    lms_cur.close()
    lms_conn.close()
except Exception as e:
    print(f"  LMS check failed: {e}")

cur.close()
conn.close()
