"""
Check for overpaid charters (customer credits).
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

conn = get_db_connection()
cur = conn.cursor()

print("=" * 80)
print("OVERPAID CHARTERS (Customer Credits)")
print("=" * 80)

# Overall stats
cur.execute("""
    SELECT COUNT(*), SUM(balance), SUM(ABS(balance))
    FROM charters
    WHERE balance < 0
""")
count, net_balance, total_credits = cur.fetchone()
print(f"\n📊 ALL OVERPAID CHARTERS:")
print(f"   Count: {count}")
print(f"   Net balance: ${net_balance:,.2f}")
print(f"   Total credits: ${total_credits:,.2f}")

# Active overpaid
cur.execute("""
    SELECT COUNT(*), SUM(balance)
    FROM charters
    WHERE cancelled = FALSE AND balance < 0
""")
active_count, active_balance = cur.fetchone()
print(f"\n📊 ACTIVE OVERPAID:")
print(f"   Count: {active_count}")
print(f"   Total credits: ${abs(active_balance or 0):,.2f}")

# Cancelled overpaid
cur.execute("""
    SELECT COUNT(*), SUM(balance)
    FROM charters
    WHERE cancelled = TRUE AND balance < 0
""")
cancelled_count, cancelled_balance = cur.fetchone()
print(f"\n📊 CANCELLED OVERPAID:")
print(f"   Count: {cancelled_count}")
print(f"   Total credits: ${abs(cancelled_balance or 0):,.2f}")

# Top 20 overpaid
cur.execute("""
    SELECT reserve_number, charter_date, total_amount_due, paid_amount, 
           balance, cancelled, status
    FROM charters
    WHERE balance < 0
    ORDER BY balance
    LIMIT 20
""")

print("\n📋 TOP 20 OVERPAID:")
print(f"\n{'Reserve':<10} {'Date':<12} {'Total':>12} {'Paid':>12} {'Balance':>12} {'Status'}")
print("-" * 80)
for row in cur.fetchall():
    reserve, charter_date, total_due, paid, balance, cancelled, status_val = row
    status = "CANCELLED" if cancelled else (status_val or "ACTIVE")
    date_str = str(charter_date) if charter_date else "N/A"
    total = total_due or 0
    paid_amt = paid or 0
    bal = balance or 0
    print(f"{reserve:<10} {date_str:<12} ${total:>10,.2f} ${paid_amt:>10,.2f} ${bal:>10,.2f} {status}")

cur.close()
conn.close()
