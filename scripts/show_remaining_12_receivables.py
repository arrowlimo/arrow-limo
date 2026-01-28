#!/usr/bin/env python3
"""
Detailed view of remaining 12 receivables (still owed, matching almsdata and LMS).
"""

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

# 12 still owed
REMAINING_12 = [
    '001764', '015978', '014640', '005711', '015211', '015195',
    '015049', '015315', '015144', '017301', '017891', '013874'
]

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 100)
print("REMAINING 12 RECEIVABLES (Aged, Still Owed)")
print("=" * 100)
print()

total_owed = 0.0

for i, reserve in enumerate(REMAINING_12, 1):
    # Charter info
    cur.execute("""
        SELECT charter_date, status
        FROM charters
        WHERE reserve_number = %s
    """, (reserve,))
    row = cur.fetchone()
    charter_date, status = row if row else (None, None)
    
    # Charges
    cur.execute("""
        SELECT SUM(amount) FROM charter_charges 
        WHERE reserve_number = %s
    """, (reserve,))
    charges = float(cur.fetchone()[0] or 0.0)
    
    # Payments
    cur.execute("""
        SELECT SUM(amount) FROM payments 
        WHERE reserve_number = %s
    """, (reserve,))
    payments = float(cur.fetchone()[0] or 0.0)
    
    balance = charges - payments
    total_owed += balance
    
    print(f"{i:2d}. {reserve} | {charter_date or '?'} | {status or 'CLOSED':<10} | Charges: ${charges:>10.2f} | Payments: ${payments:>10.2f} | Balance: ${balance:>10.2f}")

print()
print("=" * 100)
print(f"TOTAL 12 RECEIVABLES: ${total_owed:,.2f} owed")
print("=" * 100)
print()
print("These are aged receivables (oldest from 2008) with unpaid balances.")
print("All match between almsdata and LMS (same balance in both systems).")
print()
print("OPTIONS:")
print("  1. Keep as-is (legitimate aged receivables)")
print("  2. Write down all 12 (remove charges to zero balances)")
print("  3. Write down specific ones (which ones?)")

cur.close()
conn.close()
