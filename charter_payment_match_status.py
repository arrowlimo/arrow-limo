#!/usr/bin/env python3
"""Charter-Payment Reconciliation: Check current match rate and balance status."""
import psycopg2
import os

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Total charters
query_total = '''
SELECT COUNT(*) as total_charters,
       SUM(total_amount_due) as total_due,
       SUM(paid_amount) as total_paid
FROM charters
WHERE total_amount_due > 0;
'''

# Charters with payments
query_with_payments = '''
SELECT COUNT(DISTINCT c.charter_id) as charters_with_payments,
       SUM(c.total_amount_due) as due,
       SUM(c.paid_amount) as paid
FROM charters c
WHERE c.total_amount_due > 0
  AND EXISTS (
    SELECT 1 FROM payments p 
    WHERE p.reserve_number = c.reserve_number
  );
'''

# Balanced charters (paid = due, within $0.10)
query_balanced = '''
SELECT COUNT(*) as balanced_count,
       SUM(c.total_amount_due) as due,
       SUM(c.paid_amount) as paid
FROM charters c
WHERE c.total_amount_due > 0
  AND ABS(c.total_amount_due - c.paid_amount) < 0.10;
'''

# Underpaid charters
query_underpaid = '''
SELECT COUNT(*) as underpaid_count,
       SUM(c.total_amount_due) as due,
       SUM(c.paid_amount) as paid,
       SUM(c.total_amount_due - c.paid_amount) as balance_due
FROM charters c
WHERE c.total_amount_due > 0
  AND (c.total_amount_due - c.paid_amount) >= 0.10;
'''

# Overpaid charters
query_overpaid = '''
SELECT COUNT(*) as overpaid_count,
       SUM(c.total_amount_due) as due,
       SUM(c.paid_amount) as paid,
       SUM(c.paid_amount - c.total_amount_due) as overpayment
FROM charters c
WHERE c.total_amount_due > 0
  AND (c.paid_amount - c.total_amount_due) >= 0.10;
'''

# Charters with NO payments but amount due
query_no_payments = '''
SELECT COUNT(*) as no_payment_count,
       SUM(c.total_amount_due) as due
FROM charters c
WHERE c.total_amount_due > 0
  AND c.paid_amount < 0.01;
'''

cur.execute(query_total)
total_charters, total_due, total_paid = cur.fetchone()

cur.execute(query_with_payments)
charters_with_payments, due_with_pmts, paid_with_pmts = cur.fetchone()

cur.execute(query_balanced)
balanced_count, balanced_due, balanced_paid = cur.fetchone()

cur.execute(query_underpaid)
underpaid_count, underpaid_due, underpaid_paid, balance_due = cur.fetchone()

cur.execute(query_overpaid)
overpaid_count, overpaid_due, overpaid_paid, overpayment = cur.fetchone()

cur.execute(query_no_payments)
no_payment_count, no_payment_due = cur.fetchone()

cur.close()
conn.close()

# Convert to float
total_charters = total_charters or 0
total_due = float(total_due) if total_due else 0
total_paid = float(total_paid) if total_paid else 0
charters_with_payments = charters_with_payments or 0
balanced_count = balanced_count or 0
balanced_due = float(balanced_due) if balanced_due else 0
balanced_paid = float(balanced_paid) if balanced_paid else 0
underpaid_count = underpaid_count or 0
underpaid_due = float(underpaid_due) if underpaid_due else 0
underpaid_paid = float(underpaid_paid) if underpaid_paid else 0
balance_due = float(balance_due) if balance_due else 0
overpaid_count = overpaid_count or 0
overpaid_due = float(overpaid_due) if overpaid_due else 0
overpaid_paid = float(overpaid_paid) if overpaid_paid else 0
overpayment = float(overpayment) if overpayment else 0
no_payment_count = no_payment_count or 0
no_payment_due = float(no_payment_due) if no_payment_due else 0

print("\n" + "=" * 120)
print("CHARTER → PAYMENT RECONCILIATION STATUS".center(120))
print("=" * 120)

print(f"\n📊 TOTAL CHARTERS (with amount due):")
print(f"   {total_charters:>6,} charters | Due: ${total_due:>12,.2f} | Paid: ${total_paid:>12,.2f}")

print(f"\n✅ BALANCED CHARTERS (paid ≈ due, within $0.10):")
print(f"   {balanced_count:>6,} charters | Due: ${balanced_due:>12,.2f} | Paid: ${balanced_paid:>12,.2f}")
match_rate = 100 * balanced_count / total_charters if total_charters > 0 else 0
print(f"   Match Rate: {match_rate:.2f}%")

print(f"\n🔴 UNDERPAID CHARTERS (balance due ≥ $0.10):")
print(f"   {underpaid_count:>6,} charters | Due: ${underpaid_due:>12,.2f} | Paid: ${underpaid_paid:>12,.2f}")
print(f"   Balance Owed: ${balance_due:>12,.2f}")

print(f"\n🟠 OVERPAID CHARTERS (paid > due by ≥ $0.10):")
print(f"   {overpaid_count:>6,} charters | Due: ${overpaid_due:>12,.2f} | Paid: ${overpaid_paid:>12,.2f}")
print(f"   Overpayment: ${overpayment:>12,.2f}")

print(f"\n❌ CHARTERS WITH NO PAYMENTS:")
print(f"   {no_payment_count:>6,} charters | Due: ${no_payment_due:>12,.2f}")

print("\n" + "=" * 120)
print("RECONCILIATION SUMMARY")
print("=" * 120)
print(f"Charter Match Rate:      {match_rate:.2f}% ({balanced_count:,} of {total_charters:,})")
print(f"Charters with Payments:  {100*charters_with_payments/total_charters:.1f}% ({charters_with_payments:,})")
print(f"Underpaid:               {100*underpaid_count/total_charters:.1f}% ({underpaid_count:,})")
print(f"Overpaid:                {100*overpaid_count/total_charters:.1f}% ({overpaid_count:,})")
print(f"No Payments:             {100*no_payment_count/total_charters:.1f}% ({no_payment_count:,})")
print("\n" + "=" * 120)

if match_rate >= 98:
    print(f"✅ TARGET MET: {match_rate:.2f}% match rate (target: 98%)")
else:
    print(f"⚠️  BELOW TARGET: {match_rate:.2f}% match rate (target: 98%)")
    print(f"   Gap: {98 - match_rate:.2f}% ({int((98-match_rate)/100*total_charters):,} charters)")
print("=" * 120 + "\n")
