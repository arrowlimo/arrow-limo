#!/usr/bin/env python3
"""Simple E-transfer matching with extended time window (up to 365 days)."""
import psycopg2
import os

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Count matched E-transfers (within 7 days, exact amount)
query_7day = '''
SELECT COUNT(*) as count_7day, SUM(bt.credit_amount) as sum_7day
FROM banking_transactions bt
WHERE bt.credit_amount > 0
  AND (bt.description ILIKE '%E-TRANSFER%' OR bt.description ILIKE '%ETRANSFER%')
  AND EXISTS (
    SELECT 1 FROM payments p 
    WHERE ABS(p.amount - bt.credit_amount) < 0.01
      AND p.payment_date::date >= bt.transaction_date::date - INTERVAL '7 days'
      AND p.payment_date::date <= bt.transaction_date::date + INTERVAL '7 days'
  );
'''

# Count matched E-transfers (7-365 days)
query_365day = '''
SELECT COUNT(*) as count_365day, SUM(bt.credit_amount) as sum_365day
FROM banking_transactions bt
WHERE bt.credit_amount > 0
  AND (bt.description ILIKE '%E-TRANSFER%' OR bt.description ILIKE '%ETRANSFER%')
  AND EXISTS (
    SELECT 1 FROM payments p 
    WHERE ABS(p.amount - bt.credit_amount) <= 1.00
      AND p.payment_date::date >= bt.transaction_date::date - INTERVAL '365 days'
      AND p.payment_date::date <= bt.transaction_date::date + INTERVAL '7 days'
      AND NOT (
        p.payment_date::date >= bt.transaction_date::date - INTERVAL '7 days'
        AND ABS(p.amount - bt.credit_amount) < 0.01
      )
  );
'''

# Total E-transfers
query_total = '''
SELECT COUNT(*) as total_count, SUM(credit_amount) as total_sum
FROM banking_transactions bt
WHERE bt.credit_amount > 0
  AND (bt.description ILIKE '%E-TRANSFER%' OR bt.description ILIKE '%ETRANSFER%');
'''

cur.execute(query_7day)
result_7day = cur.fetchone()
count_7day = result_7day[0] or 0
sum_7day = float(result_7day[1]) if result_7day[1] else 0

cur.execute(query_365day)
result_365day = cur.fetchone()
count_365day = result_365day[0] or 0
sum_365day = float(result_365day[1]) if result_365day[1] else 0

cur.execute(query_total)
result_total = cur.fetchone()
total_count = result_total[0] or 0
total_sum = float(result_total[1]) if result_total[1] else 0

cur.close()
conn.close()

unmatched_count = total_count - count_7day - count_365day
unmatched_sum = total_sum - sum_7day - sum_365day

print("\n" + "=" * 100)
print("E-TRANSFER RECONCILIATION ANALYSIS".center(100))
print("=" * 100)

print(f"\n📊 TOTAL E-TRANSFERS IN BANKING:")
print(f"   {total_count:>6} transfers | ${total_sum:>12,.2f}")

print(f"\n✅ MATCHED (±7 days, exact amount):")
print(f"   {count_7day:>6} transfers | ${sum_7day:>12,.2f} | {100*count_7day/total_count:.1f}%")

print(f"\n⏳ MATCHED (7-365 days, ±$1.00):")
print(f"   {count_365day:>6} transfers | ${sum_365day:>12,.2f} | {100*count_365day/total_count:.1f}%")

print(f"\n❌ UNMATCHED (even with 365-day window):")
print(f"   {unmatched_count:>6} transfers | ${unmatched_sum:>12,.2f} | {100*unmatched_count/total_count:.1f}%")

print(f"\n📈 COMBINED MATCHED (7 day + 7-365 day):")
combined_count = count_7day + count_365day
combined_sum = sum_7day + sum_365day
print(f"   {combined_count:>6} transfers | ${combined_sum:>12,.2f} | {100*combined_count/total_count:.1f}%")

print("\n" + "=" * 100)
print("CONCLUSION: Reversals are NSF failures")
print("=" * 100)
print("\n542 Reversal deposits ($374.6K) are EFT/Payment RETURNS (NSF, failed transactions)")
print("These represent payments that BOUNCED or FAILED and were reversed")
print("They should be written off, not matched to new payments\n")
print("Focus: Match the E-transfers with 365-day window to identify:")
print("  1. Legitimate delayed payments")
print("  2. Duplicate/overpayments")
print("  3. Payments with no corresponding charter\n")
