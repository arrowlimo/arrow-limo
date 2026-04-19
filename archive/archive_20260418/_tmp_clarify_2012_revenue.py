#!/usr/bin/env python3
"""
Verify: are the payments from 2012 or applied to 2012 charters?
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

print("=== OPTION 1: Payments received in 2012 for any charter ===")
query1 = """
SELECT 
    COUNT(*) as payment_count,
    COALESCE(SUM(amount), 0) as total_amount
FROM charter_payments
WHERE EXTRACT(YEAR FROM payment_date) = 2012;
"""
cur.execute(query1)
count1, amount1 = cur.fetchone()
print(f"Payments received in 2012: {count1}")
print(f"Total amount: ${amount1:,.2f}\n")

print("=== OPTION 2: All payments applied to 2012 charters (whenever received) ===")
query2 = """
SELECT 
    COUNT(*) as payment_count,
    COALESCE(SUM(cp.amount), 0) as total_amount
FROM charter_payments cp
INNER JOIN charters c ON cp.charter_id = c.reserve_number
WHERE EXTRACT(YEAR FROM c.charter_date) = 2012;
"""
cur.execute(query2)
count2, amount2 = cur.fetchone()
print(f"Payments to 2012 charters: {count2}")
print(f"Total amount: ${amount2:,.2f}\n")

print("=== OPTION 3: Revenue from 2012 charters ===")
query3 = """
SELECT 
    COUNT(*) as charter_count,
    COALESCE(SUM(COALESCE(grand_total, total_amount_due, 0)), 0) as total_revenue
FROM charters
WHERE EXTRACT(YEAR FROM charter_date) = 2012;
"""
cur.execute(query3)
count3, revenue3 = cur.fetchone()
print(f"2012 charters: {count3}")
print(f"Total revenue: ${revenue3:,.2f}\n")

print("=== CLARIFICATION ===")
print("The exact revenue for 2012 depends on definition:")
print(f"1. Payments RECEIVED in 2012: ${amount1:,.2f}")
print(f"2. Total revenue from charters booked in 2012: ${revenue3:,.2f}")

cur.close()
conn.close()
