#!/usr/bin/env python3
"""
Analyze charter-payment matching status.
"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("=" * 100)
print("CHARTER-PAYMENT MATCHING ANALYSIS")
print("=" * 100)

# Total payments
cur.execute("SELECT COUNT(*), SUM(amount) FROM payments WHERE amount IS NOT NULL")
total_payments, total_amount = cur.fetchone()
print(f"\n📊 PAYMENTS OVERVIEW:")
print(f"  Total payments: {total_payments:,}")
print(f"  Total amount: ${total_amount or 0:,.2f}")

# Payments with charter_id
cur.execute("SELECT COUNT(*), SUM(amount) FROM payments WHERE charter_id IS NOT NULL AND amount IS NOT NULL")
with_charter_id, charter_id_amt = cur.fetchone()
print(f"\n  With charter_id: {with_charter_id:,} ({with_charter_id/total_payments*100:.1f}%)")
print(f"    Amount: ${charter_id_amt or 0:,.2f}")

# Payments with reserve_number
cur.execute("SELECT COUNT(*), SUM(amount) FROM payments WHERE reserve_number IS NOT NULL AND amount IS NOT NULL")
with_reserve, reserve_amt = cur.fetchone()
print(f"\n  With reserve_number: {with_reserve:,} ({with_reserve/total_payments*100:.1f}%)")
print(f"    Amount: ${reserve_amt or 0:,.2f}")

# Payments with NEITHER charter_id NOR reserve_number
cur.execute("SELECT COUNT(*), SUM(amount) FROM payments WHERE (charter_id IS NULL AND reserve_number IS NULL) AND amount IS NOT NULL")
orphan_payments, orphan_amt = cur.fetchone()
print(f"\n  ⚠️  Orphan (no charter_id AND no reserve_number): {orphan_payments:,} ({orphan_payments/total_payments*100:.1f}%)")
print(f"    Amount: ${orphan_amt or 0:,.2f}")

# Payments where reserve_number doesn't match any charter
cur.execute("""
    SELECT COUNT(*), SUM(p.amount)
    FROM payments p
    LEFT JOIN charters c ON p.reserve_number = c.reserve_number
    WHERE p.reserve_number IS NOT NULL 
      AND c.charter_id IS NULL
      AND p.amount IS NOT NULL
""")
unmatched_reserve, unmatched_reserve_amt = cur.fetchone()
print(f"\n  ⚠️  Reserve_number not in charters table: {unmatched_reserve:,} ({unmatched_reserve/total_payments*100:.1f}%)")
print(f"    Amount: ${unmatched_reserve_amt or 0:,.2f}")

print("\n" + "=" * 100)
print("📊 CHARTERS OVERVIEW:")
print("=" * 100)

# Total charters
cur.execute("SELECT COUNT(*) FROM charters")
total_charters = cur.fetchone()[0]
print(f"  Total charters: {total_charters:,}")

# Charters with payments (via reserve_number)
cur.execute("""
    SELECT COUNT(DISTINCT c.charter_id)
    FROM charters c
    INNER JOIN payments p ON p.reserve_number = c.reserve_number
    WHERE p.amount IS NOT NULL
""")
charters_with_payments = cur.fetchone()[0]
print(f"\n  Charters with payments: {charters_with_payments:,} ({charters_with_payments/total_charters*100:.1f}%)")

# Charters without payments
charters_without = total_charters - charters_with_payments
print(f"  Charters without payments: {charters_without:,} ({charters_without/total_charters*100:.1f}%)")

# Charters with balance but no payments
cur.execute("""
    SELECT COUNT(*)
    FROM charters c
    LEFT JOIN payments p ON p.reserve_number = c.reserve_number
    WHERE c.balance > 0
      AND p.payment_id IS NULL
""")
balance_no_payment = cur.fetchone()[0]
print(f"\n  ⚠️  Charters with balance > 0 but NO payments: {balance_no_payment:,}")

# Charters with payments but balance still > 0 (underpaid)
cur.execute("""
    SELECT COUNT(DISTINCT c.charter_id)
    FROM charters c
    INNER JOIN payments p ON p.reserve_number = c.reserve_number
    WHERE c.balance > 0
""")
underpaid_charters = cur.fetchone()[0]
print(f"  Charters with payments but balance > 0 (underpaid): {underpaid_charters:,}")

print("\n" + "=" * 100)
print("🔍 SAMPLE ORPHAN PAYMENTS (first 20):")
print("=" * 100)

cur.execute("""
    SELECT payment_id, payment_date, amount, payment_method, 
           square_customer_name, square_payment_id, notes
    FROM payments
    WHERE (charter_id IS NULL AND reserve_number IS NULL)
      AND amount IS NOT NULL
    ORDER BY payment_date DESC, amount DESC
    LIMIT 20
""")
print(f"{'ID':<8} {'Date':<12} {'Amount':<14} {'Method':<20} {'Customer/Notes'[:40]}")
print("-" * 100)
for row in cur.fetchall():
    pid, pdate, amt, method, customer, sq_id, notes = row
    customer_display = (customer or notes or '')[:40]
    method_display = (method or '')[:20]
    print(f"{pid:<8} {str(pdate):<12} ${amt:>12.2f} {method_display:<20} {customer_display}")

print("\n" + "=" * 100)
print("🔍 SAMPLE UNMATCHED RESERVE NUMBERS (first 20):")
print("=" * 100)

cur.execute("""
    SELECT p.payment_id, p.payment_date, p.reserve_number, p.amount, p.payment_method
    FROM payments p
    LEFT JOIN charters c ON p.reserve_number = c.reserve_number
    WHERE p.reserve_number IS NOT NULL 
      AND c.charter_id IS NULL
      AND p.amount IS NOT NULL
    ORDER BY p.payment_date DESC, p.amount DESC
    LIMIT 20
""")
print(f"{'ID':<8} {'Date':<12} {'Reserve#':<12} {'Amount':<14} {'Method'[:20]}")
print("-" * 100)
for row in cur.fetchall():
    pid, pdate, reserve, amt, method = row
    method_display = (method or '')[:20]
    print(f"{pid:<8} {str(pdate):<12} {reserve:<12} ${amt:>12.2f} {method_display}")

cur.close()
conn.close()
