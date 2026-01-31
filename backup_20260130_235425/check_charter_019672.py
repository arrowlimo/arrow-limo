#!/usr/bin/env python
"""Check charter 019672 date."""
import psycopg2

conn = psycopg2.connect(
    dbname='almsdata',
    user='postgres', 
    password='***REDACTED***',
    host='localhost'
)
cur = conn.cursor()

cur.execute("""
    SELECT reserve_number, charter_date, total_amount_due, paid_amount, balance, status
    FROM charters 
    WHERE reserve_number = '019672'
""")

row = cur.fetchone()
if row:
    print(f"Reserve: {row[0]}")
    print(f"Charter Date: {row[1]}")
    print(f"Total Due: ${row[2]:.2f}")
    print(f"Paid: ${row[3]:.2f}")
    print(f"Balance: ${row[4]:.2f}")
    print(f"Status: {row[5]}")
else:
    print("Charter 019672 not found")

cur.close()
conn.close()
