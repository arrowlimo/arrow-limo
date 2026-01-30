"""
Compute charter balance status summary.
Reports counts and totals for zero, positive, and negative balances based on
charters.balance and charters.total_amount_due/paid_amount.
Also lists a small sample of unsettled charters.
"""

import psycopg2


def get_db():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***",
    )


def fmt_money(n):
    return f"${float(n):,.2f}" if n is not None else "$0.00"


print("=" * 80)
print("CHARTER BALANCE STATUS")
print("=" * 80)

conn = get_db()
cur = conn.cursor()

# Recompute summary from current charters table
cur.execute(
    """
    SELECT 
        COUNT(*),
        SUM(CASE WHEN ABS(balance) <= 0.01 THEN 1 ELSE 0 END) AS zero_count,
        SUM(CASE WHEN balance > 0.01 THEN 1 ELSE 0 END) AS pos_count,
        SUM(CASE WHEN balance < -0.01 THEN 1 ELSE 0 END) AS neg_count,
        SUM(balance) AS net_balance,
        SUM(CASE WHEN balance > 0.01 THEN balance ELSE 0 END) AS total_owed,
        SUM(CASE WHEN balance < -0.01 THEN balance ELSE 0 END) AS total_credit
    FROM charters
    """
)
row = cur.fetchone()

total, zero_count, pos_count, neg_count, net_balance, total_owed, total_credit = row

print(f"Total charters: {total:,}")
print(f"Zero balance:  {zero_count:,}")
print(f"Positive (>0.01): {pos_count:,}")
print(f"Negative (<-0.01): {neg_count:,}")
print(f"Net balance across all charters: {fmt_money(net_balance)}")
print(f"Total owed (sum of positives): {fmt_money(total_owed)}")
print(f"Total credits (sum of negatives): {fmt_money(total_credit)}")

# Sample unresolved: top 10 by absolute balance
cur.execute(
    """
    SELECT reserve_number, charter_id, total_amount_due, paid_amount, balance
    FROM charters
    WHERE ABS(balance) > 0.01
    ORDER BY ABS(balance) DESC
    LIMIT 10
    """
)
rows = cur.fetchall()

print("\n" + "=" * 80)
print("TOP UNSETTLED CHARTERS (by absolute balance)")
print("=" * 80)

if not rows:
    print("All charters have zero balance within $0.01 tolerance.")
else:
    print(f"{'Reserve':<10} {'CharterID':<10} {'Total Due':>12} {'Paid':>12} {'Balance':>12}")
    print("-" * 60)
    for r in rows:
        reserve, cid, due, paid, bal = r
        print(f"{reserve or 'NULL':<10} {str(cid):<10} {fmt_money(due):>12} {fmt_money(paid):>12} {fmt_money(bal):>12}")

# Cross-check: recompute paid via payments sum where possible
print("\n" + "=" * 80)
print("CROSS-CHECK: charters.paid_amount vs SUM(payments.amount) by reserve_number")
print("=" * 80)

cur.execute(
    """
    WITH pay AS (
        SELECT reserve_number, COALESCE(SUM(amount),0) AS sum_pay
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number
    )
    SELECT c.reserve_number, c.charter_id, c.paid_amount, p.sum_pay, (COALESCE(c.paid_amount,0) - COALESCE(p.sum_pay,0)) AS diff
    FROM charters c
    LEFT JOIN pay p ON p.reserve_number = c.reserve_number
    WHERE ABS(COALESCE(c.paid_amount,0) - COALESCE(p.sum_pay,0)) > 0.01
    ORDER BY ABS(COALESCE(c.paid_amount,0) - COALESCE(p.sum_pay,0)) DESC
    LIMIT 10
    """
)
rows2 = cur.fetchall()

if not rows2:
    print("Paid amount matches payments sum for all charters (within $0.01).")
else:
    print(f"{'Reserve':<10} {'CharterID':<10} {'CharterPaid':>12} {'SumPayments':>12} {'Diff':>12}")
    print("-" * 70)
    for r in rows2:
        reserve, cid, paid_amt, sum_pay, diff = r
        print(f"{reserve or 'NULL':<10} {str(cid):<10} {fmt_money(paid_amt):>12} {fmt_money(sum_pay):>12} {fmt_money(diff):>12}")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("CHECK COMPLETE")
print("=" * 80)
