#!/usr/bin/env python3
"""Show credit_lines table contents."""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM credit_lines")
count = cur.fetchone()[0]

cur.execute("""
    SELECT account_name, bank_name, credit_limit, current_balance, 
           interest_rate, business_percentage, is_active 
    FROM credit_lines 
    ORDER BY account_name
""")
rows = cur.fetchall()

print(f"credit_lines table: {count} rows\n")
for r in rows:
    print(f"  {r[0]:30} | {r[1]:15} | Limit: ${r[2]:,.2f} | Balance: ${r[3]:,.2f} | Rate: {r[4]}% | Biz: {r[5]}% | Active: {r[6]}")

cur.close()
conn.close()
