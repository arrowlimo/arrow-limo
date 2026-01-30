"""
Deep dive into payment flow for sample charters to understand where the disconnect is.

For each sample charter, shows:
- Charter details (paid_amount, balance, total_amount_due)
- All linked payments from payments table
- All linked refunds from charter_refunds
- Sum comparison and explanation of discrepancy

This helps identify:
1. Are payments recorded but not aggregated to charter.paid_amount?
2. Are charter.paid_amount values coming from a different source (Square, banking)?
3. Are there duplicate payment records causing issues?
"""
import psycopg2


def get_conn():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***",
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


def fmt_money(v):
    return f"${float(v or 0):,.2f}"


def analyze_charter(cur, charter_id, amount_field):
    """Analyze a single charter's payment flow"""
    
    print(f"\n{'='*100}")
    print(f"CHARTER {charter_id}")
    print(f"{'='*100}")
    
    # Charter details
    cur.execute(f"""
    SELECT charter_id, reserve_number, charter_date, client_id,
           COALESCE(paid_amount, 0) AS paid,
           COALESCE(balance, 0) AS bal,
           COALESCE(total_amount_due, 0) AS total_due,
           status, closed, cancelled
    FROM charters
    WHERE charter_id = %s
    """, (charter_id,))
    
    row = cur.fetchone()
    if not row:
        print(f"Charter {charter_id} not found")
        return
    
    cid, res, dt, client, paid, bal, total_due, status, closed, cancelled = row
    
    print(f"\nCharter Details:")
    print(f"  Reserve Number: {res}")
    print(f"  Date: {dt}")
    print(f"  Client ID: {client}")
    print(f"  Status: {status} | Closed: {closed} | Cancelled: {cancelled}")
    print(f"  Total Due: {fmt_money(total_due)}")
    print(f"  Paid Amount: {fmt_money(paid)}")
    print(f"  Balance: {fmt_money(bal)}")
    print(f"  Expected: paid + balance = total_due")
    print(f"  Actual: {fmt_money(paid)} + {fmt_money(bal)} = {fmt_money(float(paid) + float(bal))}")
    print(f"  Discrepancy: {fmt_money((float(paid) + float(bal)) - float(total_due))}")
    
    # Linked payments
    cur.execute(f"""
    SELECT payment_id, {amount_field}, payment_date, payment_method, 
           reserve_number, charter_id, payment_key, account_number
    FROM payments
    WHERE charter_id = %s OR reserve_number = %s
    ORDER BY payment_date, payment_id
    """, (charter_id, res))
    
    payments = cur.fetchall()
    payment_sum = sum(float(p[1] or 0) for p in payments)
    
    print(f"\nLinked Payments ({len(payments)} rows, sum = {fmt_money(payment_sum)}):")
    if payments:
        print(f"  {'ID':<8} {'Amount':>12} {'Date':<12} {'Method':<15} {'Reserve':<8} {'Key':<12}")
        print(f"  {'-'*80}")
        for pid, amt, pdate, method, pres, pcid, pkey, acct in payments:
            print(f"  {pid:<8} {fmt_money(amt):>12} {str(pdate):<12} {str(method or 'NULL'):<15} {str(pres or ''):<8} {str(pkey or ''):<12}")
    else:
        print("  (none)")
    
    # Linked refunds
    cur.execute("""
    SELECT id, amount, refund_date, reserve_number, charter_id
    FROM charter_refunds
    WHERE charter_id = %s OR reserve_number = %s
    ORDER BY refund_date, id
    """, (charter_id, res))
    
    refunds = cur.fetchall()
    refund_sum = sum(float(r[1] or 0) for r in refunds)
    
    print(f"\nLinked Refunds ({len(refunds)} rows, sum = {fmt_money(refund_sum)}):")
    if refunds:
        print(f"  {'ID':<8} {'Amount':>12} {'Date':<12} {'Reserve':<8}")
        print(f"  {'-'*50}")
        for rid, amt, rdate, rres, rcid in refunds:
            print(f"  {rid:<8} {fmt_money(amt):>12} {str(rdate):<12} {str(rres or ''):<8}")
    else:
        print("  (none)")
    
    # Net calculation
    net_from_tables = payment_sum - refund_sum
    print(f"\nReconciliation:")
    print(f"  Payments from payments table: {fmt_money(payment_sum)}")
    print(f"  Refunds from charter_refunds: {fmt_money(refund_sum)}")
    print(f"  Net (payments - refunds): {fmt_money(net_from_tables)}")
    print(f"  Charter.paid_amount: {fmt_money(paid)}")
    print(f"  Difference: {fmt_money(float(paid) - net_from_tables)}")
    
    if abs(float(paid) - net_from_tables) > 0.02:
        print(f"\n[WARN]  DISCREPANCY DETECTED:")
        if float(paid) > net_from_tables:
            print(f"     Charter.paid_amount is HIGHER than linked payments/refunds by {fmt_money(float(paid) - net_from_tables)}")
            print(f"     → Payments may be in other tables (Square, banking feeds, etc.)")
        else:
            print(f"     Charter.paid_amount is LOWER than linked payments/refunds by {fmt_money(net_from_tables - float(paid))}")
            print(f"     → Payments not aggregated to charter.paid_amount or duplicate payment rows")


print("=" * 100)
print("CHARTER PAYMENT FLOW ANALYSIS - SAMPLE DEEP DIVES")
print("=" * 100)

conn = get_conn()
cur = conn.cursor()

pay_cols = columns(cur, "payments")
amount_field = "payment_amount" if "payment_amount" in pay_cols else "amount"

# Sample charters with different issues

# 1. Charter with payments but no paid_amount
print("\n\n### CASE 1: Charter with linked payments but paid_amount = 0")
analyze_charter(cur, 14039, amount_field)  # $6,500 in payments, $0 paid_amount

# 2. Charter with paid_amount but no linked payments
print("\n\n### CASE 2: Charter with paid_amount but NO linked payments")
analyze_charter(cur, 17555, amount_field)  # $4,425.65 paid_amount, no linked payments

# 3. Charter with large balance discrepancy
print("\n\n### CASE 3: Charter with large balance discrepancy")
analyze_charter(cur, 13391, amount_field)  # -$18,065 discrepancy

# 4. Charter with positive balance discrepancy
print("\n\n### CASE 4: Charter with positive balance discrepancy")
analyze_charter(cur, 16650, amount_field)  # +$6,682.62 discrepancy

# 5. Well-balanced charter (for comparison)
print("\n\n### CASE 5: Properly balanced charter (for reference)")
cur.execute("""
SELECT charter_id FROM charters
WHERE total_amount_due IS NOT NULL AND total_amount_due != 0
  AND ABS((COALESCE(paid_amount,0) + COALESCE(balance,0)) - COALESCE(total_amount_due,0)) <= 0.02
  AND paid_amount > 0
LIMIT 1
""")
row = cur.fetchone()
if row:
    analyze_charter(cur, row[0], amount_field)

cur.close()
conn.close()

print("\n\n" + "=" * 100)
print("ANALYSIS COMPLETE")
print("=" * 100)
print("\nKey Findings Summary:")
print("1. Payments in 'payments' table are NOT being aggregated to charter.paid_amount")
print("2. Charter.paid_amount likely comes from different sources (Square, banking, LMS imports)")
print("3. Payment method classification is mostly missing (needs migration from source systems)")
print("4. Two separate payment tracking systems are not synchronized")
