"""
Comprehensive charter payment integrity verification.

Checks:
1. Are all payments linked to charters (via reserve_number/charter_id) properly recorded?
2. Do payment methods exist and are they classified (CC, e-transfer, cash, etc.)?
3. Do payments + refunds balance against charter.paid_amount, charter.balance, charter.total_amount_due?
4. Are there charters with payments but no paid_amount recorded?
5. Are there charters with paid_amount but no linked payments?

Reports:
- Charter payment completeness statistics
- Payment method classification breakdown
- Balance reconciliation (payments - refunds vs charter.paid_amount)
- Discrepancy examples for manual review
"""
import psycopg2
from decimal import Decimal


def get_conn():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***",
    )


def columns(cur, table):
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
        """,
        (table,),
    )
    return {r[0] for r in cur.fetchall()}


def pick_payment_amount_field(cols):
    if "payment_amount" in cols:
        return "payment_amount"
    if "amount" in cols:
        return "amount"
    return None


def fmt_money(v):
    return f"${float(v or 0):,.2f}"


print("=" * 100)
print("CHARTER PAYMENT INTEGRITY VERIFICATION")
print("=" * 100)

conn = get_conn()
cur = conn.cursor()

# Schema discovery
pay_cols = columns(cur, "payments")
char_cols = columns(cur, "charters")
ref_cols = columns(cur, "charter_refunds")

amount_field = pick_payment_amount_field(pay_cols)
if not amount_field:
    print("ERROR: payments table has no amount/payment_amount column")
    raise SystemExit(1)

has_payment_method = "payment_method" in pay_cols or "pymt_type" in pay_cols
payment_method_field = "payment_method" if "payment_method" in pay_cols else ("pymt_type" if "pymt_type" in pay_cols else None)

has_charter_paid = "paid_amount" in char_cols
has_charter_balance = "balance" in char_cols
has_charter_total = "total_amount_due" in char_cols

print("\n1. PAYMENT LINKAGE COVERAGE")
print("-" * 100)

# Total payments and linked payments
cur.execute(f"""
SELECT 
  COUNT(*) AS total_payments,
  COUNT(CASE WHEN reserve_number IS NOT NULL OR charter_id IS NOT NULL THEN 1 END) AS linked_payments,
  SUM({amount_field}) AS total_amount,
  SUM(CASE WHEN reserve_number IS NOT NULL OR charter_id IS NOT NULL THEN {amount_field} END) AS linked_amount
FROM payments
WHERE {amount_field} != 0
""")
total_pay, linked_pay, total_amt, linked_amt = cur.fetchone()
link_pct = (linked_pay / total_pay * 100) if total_pay else 0
amt_pct = (float(linked_amt or 0) / float(total_amt or 0) * 100) if total_amt else 0

print(f"Total payments (non-zero): {total_pay:,}")
print(f"Linked to charters: {linked_pay:,} ({link_pct:.2f}%)")
print(f"Total payment amount: {fmt_money(total_amt)}")
print(f"Linked payment amount: {fmt_money(linked_amt)} ({amt_pct:.2f}%)")

print("\n2. PAYMENT METHOD CLASSIFICATION")
print("-" * 100)

if payment_method_field:
    cur.execute(f"""
    SELECT 
      COALESCE({payment_method_field}, 'NULL/MISSING') AS method,
      COUNT(*) AS count,
      SUM({amount_field}) AS total_amount
    FROM payments
    WHERE reserve_number IS NOT NULL OR charter_id IS NOT NULL
    GROUP BY {payment_method_field}
    ORDER BY SUM({amount_field}) DESC NULLS LAST
    """)
    
    print(f"{'Payment Method':<20} {'Count':>10} {'Total Amount':>20}")
    print("-" * 50)
    for method, cnt, amt in cur.fetchall():
        print(f"{str(method):<20} {cnt:>10,} {fmt_money(amt):>20}")
    
    # Count missing payment methods
    cur.execute(f"""
    SELECT COUNT(*) 
    FROM payments
    WHERE (reserve_number IS NOT NULL OR charter_id IS NOT NULL)
      AND {payment_method_field} IS NULL
    """)
    missing_method = cur.fetchone()[0]
    if missing_method > 0:
        print(f"\n[WARN]  {missing_method:,} linked payments missing payment method classification")
else:
    print("[WARN]  No payment_method/pymt_type column found in payments table")

print("\n3. REFUND LINKAGE COVERAGE")
print("-" * 100)

if "amount" in ref_cols:
    cur.execute("""
    SELECT 
      COUNT(*) AS total_refunds,
      COUNT(CASE WHEN reserve_number IS NOT NULL OR charter_id IS NOT NULL THEN 1 END) AS linked_refunds,
      SUM(amount) AS total_amount,
      SUM(CASE WHEN reserve_number IS NOT NULL OR charter_id IS NOT NULL THEN amount END) AS linked_amount
    FROM charter_refunds
    """)
    total_ref, linked_ref, total_ref_amt, linked_ref_amt = cur.fetchone()
    ref_link_pct = (linked_ref / total_ref * 100) if total_ref else 0
    ref_amt_pct = (float(linked_ref_amt or 0) / float(total_ref_amt or 0) * 100) if total_ref_amt else 0
    
    print(f"Total refunds: {total_ref:,}")
    print(f"Linked to charters: {linked_ref:,} ({ref_link_pct:.2f}%)")
    print(f"Total refund amount: {fmt_money(total_ref_amt)}")
    print(f"Linked refund amount: {fmt_money(linked_ref_amt)} ({ref_amt_pct:.2f}%)")
else:
    print("[WARN]  charter_refunds table has no amount column")
    total_ref_amt = 0
    linked_ref_amt = 0

print("\n4. CHARTER BALANCE RECONCILIATION")
print("-" * 100)

if has_charter_paid:
    # Compare sum of payments-refunds vs sum of charter.paid_amount
    cur.execute(f"""
    WITH charter_payments AS (
      SELECT 
        COALESCE(charter_id, (SELECT charter_id FROM charters WHERE reserve_number = payments.reserve_number LIMIT 1)) AS cid,
        SUM({amount_field}) AS payment_total
      FROM payments
      WHERE (reserve_number IS NOT NULL OR charter_id IS NOT NULL)
        AND {amount_field} > 0
      GROUP BY COALESCE(charter_id, (SELECT charter_id FROM charters WHERE reserve_number = payments.reserve_number LIMIT 1))
    ),
    charter_refunds_agg AS (
      SELECT 
        COALESCE(charter_id, (SELECT charter_id FROM charters WHERE reserve_number = charter_refunds.reserve_number LIMIT 1)) AS cid,
        SUM(amount) AS refund_total
      FROM charter_refunds
      WHERE reserve_number IS NOT NULL OR charter_id IS NOT NULL
      GROUP BY COALESCE(charter_id, (SELECT charter_id FROM charters WHERE reserve_number = charter_refunds.reserve_number LIMIT 1))
    )
    SELECT 
      COUNT(*) AS charter_count,
      SUM(c.paid_amount) AS charter_paid_sum,
      SUM(COALESCE(cp.payment_total, 0)) AS linked_payment_sum,
      SUM(COALESCE(cr.refund_total, 0)) AS linked_refund_sum,
      SUM(COALESCE(cp.payment_total, 0) - COALESCE(cr.refund_total, 0)) AS net_linked
    FROM charters c
    LEFT JOIN charter_payments cp ON cp.cid = c.charter_id
    LEFT JOIN charter_refunds_agg cr ON cr.cid = c.charter_id
    WHERE c.paid_amount IS NOT NULL AND c.paid_amount != 0
    """)
    
    charter_cnt, charter_paid_sum, linked_pay_sum, linked_ref_sum, net_linked = cur.fetchone()
    
    print(f"Charters with paid_amount > 0: {charter_cnt:,}")
    print(f"Sum of charter.paid_amount: {fmt_money(charter_paid_sum)}")
    print(f"Sum of linked payments (+): {fmt_money(linked_pay_sum)}")
    print(f"Sum of linked refunds (-): {fmt_money(linked_ref_sum)}")
    print(f"Net linked (payments - refunds): {fmt_money(net_linked)}")
    
    delta = float(charter_paid_sum or 0) - float(net_linked or 0)
    print(f"\n[WARN]  Delta (charter.paid_amount - net linked): {fmt_money(delta)}")
    
    if abs(delta) > 1.0:
        print(f"   This indicates payments/refunds not fully captured in payments/charter_refunds tables")

print("\n5. CHARTERS WITH PAYMENTS BUT NO PAID_AMOUNT")
print("-" * 100)

if has_charter_paid:
    cur.execute(f"""
    WITH charter_payments AS (
      SELECT 
        COALESCE(charter_id, (SELECT charter_id FROM charters WHERE reserve_number = payments.reserve_number LIMIT 1)) AS cid,
        SUM({amount_field}) AS payment_total,
        COUNT(*) AS payment_count
      FROM payments
      WHERE (reserve_number IS NOT NULL OR charter_id IS NOT NULL)
        AND {amount_field} > 0
      GROUP BY COALESCE(charter_id, (SELECT charter_id FROM charters WHERE reserve_number = payments.reserve_number LIMIT 1))
    )
    SELECT COUNT(*)
    FROM charters c
    JOIN charter_payments cp ON cp.cid = c.charter_id
    WHERE COALESCE(c.paid_amount, 0) = 0
      AND cp.payment_total > 0
    """)
    
    no_paid_amt_count = cur.fetchone()[0]
    print(f"Charters with linked payments but paid_amount = 0: {no_paid_amt_count:,}")
    
    if no_paid_amt_count > 0:
        print("\nSample 10:")
        cur.execute(f"""
        WITH charter_payments AS (
          SELECT 
            COALESCE(charter_id, (SELECT charter_id FROM charters WHERE reserve_number = payments.reserve_number LIMIT 1)) AS cid,
            SUM({amount_field}) AS payment_total,
            COUNT(*) AS payment_count
          FROM payments
          WHERE (reserve_number IS NOT NULL OR charter_id IS NOT NULL)
            AND {amount_field} > 0
          GROUP BY COALESCE(charter_id, (SELECT charter_id FROM charters WHERE reserve_number = payments.reserve_number LIMIT 1))
        )
        SELECT c.charter_id, c.reserve_number, c.charter_date, 
               COALESCE(c.paid_amount, 0) AS paid_amt,
               cp.payment_total, cp.payment_count
        FROM charters c
        JOIN charter_payments cp ON cp.cid = c.charter_id
        WHERE COALESCE(c.paid_amount, 0) = 0
          AND cp.payment_total > 0
        ORDER BY cp.payment_total DESC
        LIMIT 10
        """)
        
        print(f"{'CharterID':<10} {'Reserve':<8} {'Date':<12} {'Paid$':>12} {'Linked$':>12} {'#Pay':>6}")
        print("-" * 70)
        for cid, res, dt, paid, linked, cnt in cur.fetchall():
            print(f"{cid:<10} {str(res or ''):<8} {str(dt):<12} {fmt_money(paid):>12} {fmt_money(linked):>12} {cnt:>6}")

print("\n6. CHARTERS WITH PAID_AMOUNT BUT NO LINKED PAYMENTS")
print("-" * 100)

if has_charter_paid:
    cur.execute(f"""
    SELECT COUNT(*)
    FROM charters c
    WHERE c.paid_amount > 0
      AND NOT EXISTS (
        SELECT 1 FROM payments p
        WHERE (p.charter_id = c.charter_id OR p.reserve_number = c.reserve_number)
          AND p.{amount_field} > 0
      )
    """)
    
    no_linked_count = cur.fetchone()[0]
    print(f"Charters with paid_amount > 0 but NO linked payments: {no_linked_count:,}")
    
    if no_linked_count > 0:
        print("\nSample 10:")
        cur.execute(f"""
        SELECT c.charter_id, c.reserve_number, c.charter_date, c.paid_amount, 
               COALESCE(c.balance, 0) AS balance,
               COALESCE(c.total_amount_due, 0) AS total_due
        FROM charters c
        WHERE c.paid_amount > 0
          AND NOT EXISTS (
            SELECT 1 FROM payments p
            WHERE (p.charter_id = c.charter_id OR p.reserve_number = c.reserve_number)
              AND p.{amount_field} > 0
          )
        ORDER BY c.paid_amount DESC
        LIMIT 10
        """)
        
        print(f"{'CharterID':<10} {'Reserve':<8} {'Date':<12} {'Paid$':>12} {'Balance':>12} {'TotalDue':>12}")
        print("-" * 76)
        for cid, res, dt, paid, bal, total in cur.fetchall():
            print(f"{cid:<10} {str(res or ''):<8} {str(dt):<12} {fmt_money(paid):>12} {fmt_money(bal):>12} {fmt_money(total):>12}")

print("\n7. BALANCE VERIFICATION (paid_amount + balance vs total_amount_due)")
print("-" * 100)

if has_charter_paid and has_charter_balance and has_charter_total:
    cur.execute("""
    SELECT 
      COUNT(*) AS total_charters,
      COUNT(CASE WHEN ABS((COALESCE(paid_amount,0) + COALESCE(balance,0)) - COALESCE(total_amount_due,0)) <= 0.02 THEN 1 END) AS balanced,
      COUNT(CASE WHEN ABS((COALESCE(paid_amount,0) + COALESCE(balance,0)) - COALESCE(total_amount_due,0)) > 0.02 THEN 1 END) AS unbalanced
    FROM charters
    WHERE total_amount_due IS NOT NULL AND total_amount_due != 0
    """)
    
    total_charters, balanced, unbalanced = cur.fetchone()
    bal_pct = (balanced / total_charters * 100) if total_charters else 0
    
    print(f"Charters with charges: {total_charters:,}")
    print(f"Balanced (paid + balance = total_due ±$0.02): {balanced:,} ({bal_pct:.2f}%)")
    print(f"Unbalanced: {unbalanced:,} ({100-bal_pct:.2f}%)")
    
    if unbalanced > 0:
        print("\nTop 10 unbalanced charters by discrepancy:")
        cur.execute("""
        SELECT charter_id, reserve_number, charter_date,
               COALESCE(paid_amount,0) AS paid,
               COALESCE(balance,0) AS bal,
               COALESCE(total_amount_due,0) AS total_due,
               (COALESCE(paid_amount,0) + COALESCE(balance,0)) - COALESCE(total_amount_due,0) AS discrepancy
        FROM charters
        WHERE total_amount_due IS NOT NULL AND total_amount_due != 0
          AND ABS((COALESCE(paid_amount,0) + COALESCE(balance,0)) - COALESCE(total_amount_due,0)) > 0.02
        ORDER BY ABS((COALESCE(paid_amount,0) + COALESCE(balance,0)) - COALESCE(total_amount_due,0)) DESC
        LIMIT 10
        """)
        
        print(f"{'CharterID':<10} {'Reserve':<8} {'Date':<12} {'Paid$':>12} {'Balance':>12} {'TotalDue':>12} {'Discrep':>12}")
        print("-" * 88)
        for cid, res, dt, paid, bal, total_due, disc in cur.fetchall():
            print(f"{cid:<10} {str(res or ''):<8} {str(dt):<12} {fmt_money(paid):>12} {fmt_money(bal):>12} {fmt_money(total_due):>12} {fmt_money(disc):>12}")

cur.close()
conn.close()

print("\n" + "=" * 100)
print("VERIFICATION COMPLETE")
print("=" * 100)
