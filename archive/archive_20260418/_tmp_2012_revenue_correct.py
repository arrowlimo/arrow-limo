#!/usr/bin/env python3
"""
Calculate total 2012 charter revenue using correct join on reserve_number.
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

# Get total revenue for 2012 charters with payments
# Join charter_payments to charters via reserve_number
query = """
SELECT 
    COALESCE(SUM(COALESCE(c.grand_total, c.total_amount_due, 0)), 0) as total_revenue,
    COUNT(DISTINCT c.charter_id) as unique_charters,
    COALESCE(SUM(cp.amount), 0) as total_paid,
    COUNT(DISTINCT cp.id) as payment_count
FROM charter_payments cp
INNER JOIN charters c ON cp.charter_id = c.reserve_number
WHERE EXTRACT(YEAR FROM c.charter_date) = 2012;
"""

cur.execute(query)
total_revenue, unique_charters, total_paid, payment_count = cur.fetchone()

print(f"\n=== 2012 CHARTERS WITH PAYMENTS ===")
print(f"Total unique charters: {unique_charters}")
print(f"Total payment records: {payment_count}")
print(f"Total charter revenue (grand_total/total_amount_due): ${total_revenue:,.2f}")
print(f"Total client payments made: ${total_paid:,.2f}")

# Get breakdown
query2 = """
SELECT 
    COUNT(DISTINCT c.charter_id) as charters_booked,
    COALESCE(SUM(COALESCE(c.grand_total, c.total_amount_due, 0)), 0) as revenue_booked
FROM charters c
WHERE EXTRACT(YEAR FROM c.charter_date) = 2012;
"""

cur.execute(query2)
all_charters, all_revenue = cur.fetchone()

print(f"\n=== ALL 2012 CHARTERS (regardless of payment status) ===")
print(f"Total charters: {all_charters}")
print(f"Total revenue booked: ${all_revenue:,.2f}")

# Calculate unpaid
unpaid = all_revenue - total_paid
print(f"\n=== SUMMARY ===")
print(f"Total 2012 revenue booked: ${all_revenue:,.2f}")
print(f"Total payments received: ${total_paid:,.2f}")
print(f"Outstanding/unpaid: ${unpaid:,.2f}")

cur.close()
conn.close()
