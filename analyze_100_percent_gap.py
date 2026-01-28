#!/usr/bin/env python3
"""Analyze ALL unbalanced charters to identify root causes and reach 100% match."""
import psycopg2
import os

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Get all unbalanced charters
query = '''
SELECT 
    c.charter_id,
    c.reserve_number,
    c.total_amount_due,
    c.paid_amount,
    (c.total_amount_due - c.paid_amount) as balance,
    c.status,
    c.pickup_time,
    COUNT(p.payment_id) as payment_count,
    COALESCE(SUM(p.amount), 0) as payment_sum,
    c.client_id
FROM charters c
LEFT JOIN payments p ON p.reserve_number = c.reserve_number
WHERE c.total_amount_due > 0
  AND ABS(c.total_amount_due - c.paid_amount) >= 0.10
GROUP BY c.charter_id, c.reserve_number, c.total_amount_due, c.paid_amount, c.status, c.pickup_time, c.client_id
ORDER BY ABS(c.total_amount_due - c.paid_amount) DESC;
'''

cur.execute(query)
results = cur.fetchall()
cur.close()
conn.close()

# Categorize issues
penny_rounding = []  # < $1.00
small_balance = []   # $1.00 - $10.00
medium_balance = []  # $10.01 - $100.00
large_balance = []   # > $100.00
no_payments = []     # 0 payments
overpaid = []        # Paid > Due

for row in results:
    charter_id, reserve, due, paid, balance, status, pickup_date, pmt_count, pmt_sum, client_id = row
    
    abs_balance = abs(balance)
    
    if pmt_count == 0:
        no_payments.append(row)
    elif balance < -0.10:  # Overpaid
        overpaid.append(row)
    elif abs_balance < 1.00:
        penny_rounding.append(row)
    elif abs_balance <= 10.00:
        small_balance.append(row)
    elif abs_balance <= 100.00:
        medium_balance.append(row)
    else:
        large_balance.append(row)

print("\n" + "=" * 140)
print("UNBALANCED CHARTERS - ROOT CAUSE ANALYSIS (Target: 100% Match)".center(140))
print("=" * 140)
print(f"\nTotal Unbalanced: {len(results)} charters")
print(f"Current Match: 97.91% | Target: 100.00% | Gap: {len(results)} charters\n")

# Summary by category
print("📊 BREAKDOWN BY ISSUE TYPE:")
print("-" * 140)
print(f"Penny Rounding (< $1.00):        {len(penny_rounding):>4} charters | ${sum(abs(r[4]) for r in penny_rounding):>10,.2f}")
print(f"Small Balance ($1-$10):          {len(small_balance):>4} charters | ${sum(abs(r[4]) for r in small_balance):>10,.2f}")
print(f"Medium Balance ($10-$100):       {len(medium_balance):>4} charters | ${sum(abs(r[4]) for r in medium_balance):>10,.2f}")
print(f"Large Balance (> $100):          {len(large_balance):>4} charters | ${sum(abs(r[4]) for r in large_balance):>10,.2f}")
print(f"No Payments:                     {len(no_payments):>4} charters | ${sum(r[2] for r in no_payments):>10,.2f}")
print(f"Overpaid:                        {len(overpaid):>4} charters | ${sum(abs(r[4]) for r in overpaid):>10,.2f}")
print("-" * 140)

# Show top issues by category
def show_category(name, data, limit=10):
    if not data:
        return
    
    print(f"\n🔍 {name} (showing top {min(len(data), limit)}):")
    print("-" * 140)
    print(f"{'Charter':<8} | {'Reserve':<8} | {'Due':>10} | {'Paid':>10} | {'Balance':>10} | {'Pmts':>5} | {'Status':<15}")
    print("-" * 140)
    
    for row in data[:limit]:
        charter_id, reserve, due, paid, balance, status, pickup_date, pmt_count, pmt_sum, client_id = row
        reserve_str = reserve or 'N/A'
        status_str = (status[:14] if status else 'Unknown')
        print(f"{charter_id:<8} | {reserve_str:<8} | ${due:>9.2f} | ${paid:>9.2f} | ${balance:>9.2f} | {pmt_count:>5} | {status_str:<15}")

show_category("LARGE BALANCES (> $100)", large_balance, 15)
show_category("MEDIUM BALANCES ($10-$100)", medium_balance, 10)
show_category("SMALL BALANCES ($1-$10)", small_balance, 10)
show_category("PENNY ROUNDING (< $1)", penny_rounding, 10)
show_category("NO PAYMENTS", no_payments, 15)
show_category("OVERPAID", overpaid, 7)

print("\n\n" + "=" * 140)
print("🎯 ACTION PLAN TO REACH 100%")
print("=" * 140)
print(f"\n1. NO PAYMENTS ({len(no_payments)} charters):")
print(f"   - Verify if cancelled/voided charters → set total_amount_due = 0")
print(f"   - Check for missing payment records in database")
print(f"   - Match to banking deposits (E-transfers, Square, etc.)")

print(f"\n2. LARGE BALANCES ({len(large_balance)} charters):")
print(f"   - Likely missing payments or incorrect charges")
print(f"   - Review charter history and payment records")
print(f"   - Check for partial payments that weren't recorded")

print(f"\n3. PENNY ROUNDING ({len(penny_rounding)} charters):")
print(f"   - Add penny rounding adjustments to charges")
print(f"   - SQL: UPDATE charters SET total_amount_due = paid_amount WHERE ABS(balance) < $1")

print(f"\n4. OVERPAID ({len(overpaid)} charters):")
print(f"   - Mark as deposits/retainers for future bookings")
print(f"   - Verify duplicate payments")
print(f"   - Issue refunds if applicable")

print("\n" + "=" * 140 + "\n")
