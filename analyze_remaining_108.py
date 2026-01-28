#!/usr/bin/env python3
"""Analyze remaining 108 unbalanced charters to reach 100% match."""
import psycopg2
import os

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Get remaining unbalanced charters
query = '''
SELECT 
    c.charter_id,
    c.reserve_number,
    c.total_amount_due,
    c.paid_amount,
    (c.total_amount_due - c.paid_amount) as balance,
    c.status,
    COUNT(p.payment_id) as payment_count,
    COALESCE(SUM(p.amount), 0) as payment_sum
FROM charters c
LEFT JOIN payments p ON p.reserve_number = c.reserve_number
WHERE c.total_amount_due > 0
  AND ABS(c.total_amount_due - c.paid_amount) >= 0.10
GROUP BY c.charter_id, c.reserve_number, c.total_amount_due, c.paid_amount, c.status
ORDER BY ABS(c.total_amount_due - c.paid_amount) ASC;
'''

cur.execute(query)
results = cur.fetchall()
cur.close()
conn.close()

# Categorize
penny_rounding = []
no_payments_uncancelled = []
partial_payments = []
overpaid = []

for row in results:
    charter_id, reserve, due, paid, balance, status, pmt_count, pmt_sum = row
    
    abs_balance = abs(balance)
    
    if abs_balance < 1.00:
        penny_rounding.append(row)
    elif pmt_count == 0:
        no_payments_uncancelled.append(row)
    elif balance < -0.10:
        overpaid.append(row)
    else:
        partial_payments.append(row)

print("\n" + "=" * 140)
print("REMAINING 108 UNBALANCED CHARTERS - PATH TO 100%".center(140))
print("=" * 140)
print(f"\nTotal Remaining: {len(results)} charters")
print(f"Current Match: 99.34% | Target: 100.00% | Gap: {len(results)} charters ({100 - 99.34:.2f}%)\n")

print("📊 BREAKDOWN:")
print("-" * 140)
print(f"Penny Rounding (< $1.00):          {len(penny_rounding):>3} charters | ${sum(abs(r[4]) for r in penny_rounding):>10,.2f} | FIX: Auto-adjust")
print(f"No Payments (uncancelled):         {len(no_payments_uncancelled):>3} charters | ${sum(r[2] for r in no_payments_uncancelled):>10,.2f} | REVIEW: Cancel or find payments")
print(f"Partial Payments:                  {len(partial_payments):>3} charters | ${sum(r[4] for r in partial_payments):>10,.2f} | REVIEW: Find missing payments")
print(f"Overpaid:                          {len(overpaid):>3} charters | ${sum(abs(r[4]) for r in overpaid):>10,.2f} | REVIEW: Retainers or refunds")
print("-" * 140)

# Show each category
def show_category(name, data, limit=None):
    if not data:
        return
    
    show_count = len(data) if limit is None else min(len(data), limit)
    print(f"\n🔍 {name} ({len(data)} total, showing {show_count}):")
    print("-" * 140)
    print(f"{'Charter':<8} | {'Reserve':<8} | {'Due':>10} | {'Paid':>10} | {'Balance':>10} | {'Pmts':>5} | {'Status':<20}")
    print("-" * 140)
    
    for row in data[:show_count]:
        charter_id, reserve, due, paid, balance, status, pmt_count, pmt_sum = row
        reserve_str = reserve or 'N/A'
        status_str = (status[:19] if status else 'Unknown')
        print(f"{charter_id:<8} | {reserve_str:<8} | ${due:>9.2f} | ${paid:>9.2f} | ${balance:>9.2f} | {pmt_count:>5} | {status_str:<20}")

show_category("PENNY ROUNDING", penny_rounding)
show_category("NO PAYMENTS (UNCANCELLED)", no_payments_uncancelled)
show_category("PARTIAL PAYMENTS", partial_payments, 20)
show_category("OVERPAID", overpaid)

print("\n\n" + "=" * 140)
print("🎯 ACTION PLAN TO REACH 100%")
print("=" * 140)

print(f"\n✅ QUICK FIX ({len(penny_rounding)} charters):")
print(f"   SQL: UPDATE charters SET total_amount_due = paid_amount")
print(f"        WHERE charter_id IN ({','.join(str(r[0]) for r in penny_rounding[:10])}, ...)")
print(f"   Impact: +{len(penny_rounding)} charters → {99.34 + 100*len(penny_rounding)/16300:.2f}%")

print(f"\n🔍 MANUAL REVIEW ({len(no_payments_uncancelled)} charters):")
print(f"   - Review each charter (likely should be cancelled)")
print(f"   - If cancelled: SET total_amount_due = 0")
print(f"   - If valid: Find missing payments in banking")

print(f"\n🔍 PARTIAL PAYMENTS ({len(partial_payments)} charters):")
print(f"   - Match to banking deposits (E-transfers, cash)")
print(f"   - Add missing payment records")
print(f"   - Or adjust charges if overstated")

print(f"\n🔍 OVERPAID ({len(overpaid)} charters):")
print(f"   - Mark as retainers/deposits")
print(f"   - Check for duplicate payments")
print(f"   - Adjust total_amount_due if charges were updated")

print("\n" + "=" * 140 + "\n")
