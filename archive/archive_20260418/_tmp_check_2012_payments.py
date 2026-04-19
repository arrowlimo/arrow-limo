#!/usr/bin/env python3
"""
Check charter_payments for 2012 data.
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

# Check charter_payments for 2012
query = """
SELECT COUNT(*), MIN(payment_date), MAX(payment_date) 
FROM charter_payments 
WHERE EXTRACT(YEAR FROM payment_date) = 2012;
"""

cur.execute(query)
count, min_date, max_date = cur.fetchone()
print(f"Charter payments in 2012: {count}")
print(f"  Min date: {min_date}")
print(f"  Max date: {max_date}")

# Check how many charter_payments don't match to charters
query2 = """
SELECT COUNT(DISTINCT cp.id) as unmatched
FROM charter_payments cp
LEFT JOIN charters c ON cp.charter_id::text = c.charter_id::text
WHERE c.charter_id IS NULL AND EXTRACT(YEAR FROM cp.payment_date) = 2012;
"""

cur.execute(query2)
unmatched = cur.fetchone()[0]
print(f"Unmatched charter_payments in 2012: {unmatched}")

# Get total paid for 2012
query3 = """
SELECT 
    COALESCE(SUM(amount), 0) as total_amount,
    COUNT(*) as payment_count
FROM charter_payments
WHERE EXTRACT(YEAR FROM payment_date) = 2012;
"""

cur.execute(query3)
total_amt, pay_count = cur.fetchone()
print(f"\nTotal payments amount in 2012: ${total_amt:,.2f}")
print(f"Total payment records: {pay_count}")

# Get total by charter_id coverage
query4 = """
SELECT 
    COUNT(DISTINCT cp.charter_id) as distinct_charter_ids,
    COALESCE(SUM(CASE WHEN c.charter_id IS NOT NULL THEN cp.amount ELSE 0 END), 0) as matched_total,
    COALESCE(SUM(CASE WHEN c.charter_id IS NULL THEN cp.amount ELSE 0 END), 0) as unmatched_total
FROM charter_payments cp
LEFT JOIN charters c ON cp.charter_id::text = c.charter_id::text
WHERE EXTRACT(YEAR FROM cp.payment_date) = 2012;
"""

cur.execute(query4)
distinct_charters, matched_total, unmatched_total = cur.fetchone()
print(f"\nCharter IDs in payments: {distinct_charters}")
print(f"Matched to charters: ${matched_total:,.2f}")
print(f"Unmatched to charters: ${unmatched_total:,.2f}")

cur.close()
conn.close()
