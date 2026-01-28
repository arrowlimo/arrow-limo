#!/usr/bin/env python3
"""Check for Jan-Feb 2013 CIBC data."""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

cur.execute("""
    SELECT 
        COUNT(*), 
        MIN(transaction_date), 
        MAX(transaction_date), 
        SUM(debit_amount), 
        SUM(credit_amount) 
    FROM banking_transactions 
    WHERE account_number = '0228362' 
    AND transaction_date >= '2013-01-01' 
    AND transaction_date <= '2013-02-28'
""")

row = cur.fetchone()

print("="*60)
print("Jan-Feb 2013 CIBC Account 0228362")
print("="*60)
print(f"Transaction count: {row[0]}")
if row[0] > 0:
    print(f"Date range: {row[1]} to {row[2]}")
    print(f"Total debits: ${float(row[3] or 0):,.2f}")
    print(f"Total credits: ${float(row[4] or 0):,.2f}")
else:
    print("NO DATA FOUND - 2013 is completely missing")

conn.close()
