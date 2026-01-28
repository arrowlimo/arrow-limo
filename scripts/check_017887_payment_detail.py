#!/usr/bin/env python3
"""
Get details of the $189.00 payment for 017887.
"""

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 90)
print("017887 PAYMENT DETAILS")
print("=" * 90)
print()

cur.execute("""
    SELECT 
        payment_id,
        reserve_number,
        payment_method,
        amount,
        payment_date,
        notes,
        created_at,
        banking_transaction_id
    FROM payments
    WHERE reserve_number = '017887'
    ORDER BY payment_date DESC
""")

payments = cur.fetchall()

if payments:
    for payment in payments:
        payment_id, reserve, method, amount, payment_date, notes, created_at, banking_id = payment
        
        print(f"Payment ID: {payment_id}")
        print(f"Reserve: {reserve}")
        print(f"Method: {method or 'NULL'}")
        print(f"Amount: ${float(amount):,.2f}")
        print(f"Payment Date: {payment_date}")
        print(f"Notes: {notes or '(empty)'}")
        print(f"Created At: {created_at}")
        print(f"Banking Transaction ID: {banking_id}")
        print()
else:
    print("No payments found for 017887")

cur.close()
conn.close()
