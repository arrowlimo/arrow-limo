#!/usr/bin/env python3
"""
List all 2012 charters that have cash payments.
"""

import psycopg2

DB_HOST = 'localhost'
DB_PORT = 5432
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = 'ArrowLimousine'

conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

# Get all 2012 charters with cash payments
query = """
SELECT 
    DISTINCT c.charter_id,
    c.reserve_number,
    c.charter_date,
    c.client_display_name,
    COALESCE(c.grand_total, c.total_amount_due, 0) as amount_owed,
    SUM(cp.amount) FILTER (WHERE LOWER(cp.payment_method) LIKE '%cash%') as cash_paid,
    SUM(cp.amount) as total_paid,
    COUNT(DISTINCT cp.id) FILTER (WHERE LOWER(cp.payment_method) LIKE '%cash%') as cash_payment_count
FROM charters c
INNER JOIN charter_payments cp ON cp.charter_id = c.reserve_number
WHERE EXTRACT(YEAR FROM c.charter_date) = 2012
  AND LOWER(cp.payment_method) LIKE '%cash%'
GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.client_display_name, c.grand_total, c.total_amount_due
ORDER BY c.charter_date, c.charter_id;
"""

cur.execute(query)
rows = cur.fetchall()

print(f"\n{'Charter':<10} {'Reserve':<12} {'Date':<12} {'Client':<30} {'Amount Owed':<14} {'Cash Paid':<14} {'Total Paid':<14} {'# Payments':<10}")
print("=" * 130)

total_cash = 0
cash_charters = 0

for charter_id, reserve, charter_date, client, owed, cash_paid, total_paid, payment_count in rows:
    if owed is None:
        owed = 0
    if cash_paid is None:
        cash_paid = 0
    if total_paid is None:
        total_paid = 0
    
    client_display = (client or "N/A")[:28]
    total_cash += float(cash_paid)
    cash_charters += 1
    
    print(f"{charter_id:<10} {reserve:<12} {str(charter_date):<12} {client_display:<30} ${float(owed):>11,.2f} ${float(cash_paid):>11,.2f} ${float(total_paid):>11,.2f} {int(payment_count):<10}")

print("=" * 130)
print(f"Total cash-paid charters in 2012: {cash_charters}")
print(f"Total cash payments: ${total_cash:,.2f}")

# Also get breakdown by payment method for all charters
print(f"\n=== ALL 2012 CHARTER PAYMENT METHODS ===")
method_query = """
SELECT 
    COALESCE(LOWER(cp.payment_method), 'unknown') as payment_method,
    COUNT(DISTINCT c.charter_id) as charter_count,
    COALESCE(SUM(cp.amount), 0) as total_amount
FROM charters c
INNER JOIN charter_payments cp ON cp.charter_id = c.reserve_number
WHERE EXTRACT(YEAR FROM c.charter_date) = 2012
GROUP BY LOWER(cp.payment_method)
ORDER BY total_amount DESC;
"""

cur.execute(method_query)
methods = cur.fetchall()
print(f"\n{'Payment Method':<30} {'Charters':<15} {'Total Amount':<15}")
print("-" * 60)
for method, count, amount in methods:
    print(f"{(method or 'N/A'):<30} {count:<15} ${float(amount):>11,.2f}")

cur.close()
conn.close()
