#!/usr/bin/env python3
"""
Check almsdata status only (not LMS).
Driver's own run = 015049
"""

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("Checking almsdata only:")
print()

reserves_check = ['001764', '005711', '015049', '015978']

for reserve in reserves_check:
    cur.execute("""
        SELECT 
            COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = %s), 0) as charges,
            COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = %s), 0) as payments
    """, (reserve, reserve))
    
    charges, payments = cur.fetchone()
    charges, payments = float(charges), float(payments)
    balance = charges - payments
    
    print(f"{reserve}: Charges ${charges:>10.2f} | Payments ${payments:>10.2f} | Balance ${balance:>10.2f}")

print()
print("Notes:")
print("  015049 = driver's own run (in almsdata)")
print("  005711 = fixed (in almsdata)")
print("  001764 = still has charges (in almsdata)")
print("  015978 = legitimate aged receivable (in almsdata)")

cur.close()
conn.close()
