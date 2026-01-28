#!/usr/bin/env python3
"""Clean E-transfer reconciliation: matched vs unmatched with 365-day window."""
import psycopg2
import os

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Total E-transfers
query_total = '''
SELECT COUNT(*) as total, SUM(credit_amount) as sum
FROM banking_transactions bt
WHERE bt.credit_amount > 0
  AND (bt.description ILIKE '%E-TRANSFER%' OR bt.description ILIKE '%ETRANSFER%');
'''

# E-transfers WITH a matching payment (±365 days, ±$1)
query_matched = '''
SELECT COUNT(DISTINCT bt.transaction_id) as matched_count, 
       SUM(DISTINCT bt.credit_amount) as matched_sum
FROM banking_transactions bt
WHERE bt.credit_amount > 0
  AND (bt.description ILIKE '%E-TRANSFER%' OR bt.description ILIKE '%ETRANSFER%')
  AND EXISTS (
    SELECT 1 FROM payments p 
    WHERE ABS(p.amount - bt.credit_amount) <= 1.00
      AND p.payment_date::date >= bt.transaction_date::date - INTERVAL '365 days'
      AND p.payment_date::date <= bt.transaction_date::date + INTERVAL '365 days'
  );
'''

# E-transfers WITHOUT any matching payment
query_unmatched = '''
SELECT COUNT(*) as unmatched_count, 
       SUM(bt.credit_amount) as unmatched_sum
FROM banking_transactions bt
WHERE bt.credit_amount > 0
  AND (bt.description ILIKE '%E-TRANSFER%' OR bt.description ILIKE '%ETRANSFER%')
  AND NOT EXISTS (
    SELECT 1 FROM payments p 
    WHERE ABS(p.amount - bt.credit_amount) <= 1.00
      AND p.payment_date::date >= bt.transaction_date::date - INTERVAL '365 days'
      AND p.payment_date::date <= bt.transaction_date::date + INTERVAL '365 days'
  );
'''

cur.execute(query_total)
total_count, total_sum = cur.fetchone()

cur.execute(query_matched)
matched_count, matched_sum = cur.fetchone()

cur.execute(query_unmatched)
unmatched_count, unmatched_sum = cur.fetchone()

cur.close()
conn.close()

total_count = total_count or 0
total_sum = float(total_sum) if total_sum else 0
matched_count = matched_count or 0
matched_sum = float(matched_sum) if matched_sum else 0
unmatched_count = unmatched_count or 0
unmatched_sum = float(unmatched_sum) if unmatched_sum else 0

print("\n" + "=" * 100)
print("E-TRANSFER RECONCILIATION (365-DAY WINDOW, ±$1.00 TOLERANCE)".center(100))
print("=" * 100)

print(f"\n📊 TOTAL E-TRANSFERS:")
print(f"   {total_count:>6} transfers | ${total_sum:>12,.2f}")

print(f"\n✅ MATCHED (found corresponding payment):")
print(f"   {matched_count:>6} transfers | ${matched_sum:>12,.2f} | {100*matched_count/total_count:.1f}%")

print(f"\n❌ UNMATCHED (no payment record):")
print(f"   {unmatched_count:>6} transfers | ${unmatched_sum:>12,.2f} | {100*unmatched_count/total_count:.1f}%")

print("\n" + "=" * 100)
print("KEY INSIGHT")
print("=" * 100)
print(f"\nOf ${total_sum:,.0f} in E-transfers:")
print(f"  ✅ {100*matched_sum/total_sum:.1f}% (${matched_sum:,.0f}) matched to payments")
print(f"  ❌ {100*unmatched_sum/total_sum:.1f}% (${unmatched_sum:,.0f}) unmatched (need investigation)")

print("\nUNMATCHED = Likely:")
print("  • Employee payments (payroll, reimbursements)")
print("  • Payments to customers (refunds)")
print("  • Payments to vendors (not from charters)")
print("  • Payments with no corresponding payment record (data quality issue)")
print("=" * 100 + "\n")
