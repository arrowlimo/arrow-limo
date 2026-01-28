#!/usr/bin/env python3
"""
Check what payments remain for these 5 reserves after deletion.
"""

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

reserves = ['017887', '017765', '018013', '015288', '015244']

print("Checking remaining payments for 5 reserves after deletion:")
print()

for reserve in reserves:
    cur.execute("""
        SELECT payment_method, amount, payment_date, notes
        FROM payments
        WHERE reserve_number = %s
        ORDER BY payment_date DESC
    """, (reserve,))
    
    payments = cur.fetchall()
    print(f"{reserve}:")
    if payments:
        for method, amt, paid, notes in payments:
            method_str = method or 'unknown'
            notes_str = f" ({notes})" if notes else ""
            print(f"  - {method_str:<20} ${float(amt):>10.2f}  {paid}{notes_str}")
    else:
        print(f"  (no payments)")
    print()

cur.close()
conn.close()
