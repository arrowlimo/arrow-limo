"""
Analyze why a high match rate by count (e.g., 98%) on reserve-linked payments/refunds
may not reconcile to expected dollar amounts.

This script computes both COUNT-based and AMOUNT-based match rates for:
- Payments (positive amounts only)
- Refunds (charter_refunds table)
And compares them to charter-side totals (sum of charters.paid_amount).

It also lists top unmatched amounts to show skew (few big items can dominate dollars).

SAFE SCHEMA ACCESS: Introspects column names to choose correct amount field (amount vs payment_amount)
"""
import psycopg2


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
    # Fallback: be explicit to avoid SQL error
    raise RuntimeError("payments table missing amount/payment_amount column")


def pick_payment_link_filters(cols):
    conds = []
    if "reserve_number" in cols:
        conds.append("reserve_number IS NOT NULL")
    if "charter_id" in cols:
        conds.append("charter_id IS NOT NULL")
    # If neither exists, nothing to link
    return " OR ".join(conds) if conds else None


def fmt_money(v):
    return f"${float(v or 0):,.2f}"


print("=" * 100)
print("PAYMENT/REFUND AMOUNT VS MATCH RATE ANALYSIS")
print("=" * 100)

conn = get_conn()
cur = conn.cursor()

# Schema discovery
pay_cols = columns(cur, "payments")
char_cols = columns(cur, "charters")
ref_cols = columns(cur, "charter_refunds")

amount_field = pick_payment_amount_field(pay_cols)
link_filter = pick_payment_link_filters(pay_cols)
if not link_filter:
    print("payments table has no link fields (reserve_number/charter_id); cannot compute match rate.")
    cur.close(); conn.close()
    raise SystemExit(1)

# Payments: positive amounts only
cur.execute(f"""
SELECT 
  COUNT(*) AS cnt_total,
  COALESCE(SUM(CASE WHEN {amount_field} > 0 THEN {amount_field} END),0) AS amt_total_pos,
  COUNT(CASE WHEN {link_filter} AND {amount_field} > 0 THEN 1 END) AS cnt_matched,
  COALESCE(SUM(CASE WHEN {link_filter} AND {amount_field} > 0 THEN {amount_field} END),0) AS amt_matched_pos,
  COUNT(CASE WHEN NOT ({link_filter}) AND {amount_field} > 0 THEN 1 END) AS cnt_unmatched,
  COALESCE(SUM(CASE WHEN NOT ({link_filter}) AND {amount_field} > 0 THEN {amount_field} END),0) AS amt_unmatched_pos
FROM payments
""")
(
    cnt_total,
    amt_total_pos,
    cnt_matched,
    amt_matched_pos,
    cnt_unmatched,
    amt_unmatched_pos,
) = cur.fetchone()

cnt_match_rate = (cnt_matched / cnt_total * 100.0) if cnt_total else 0.0
amt_match_rate = (
    (float(amt_matched_pos) / float(amt_total_pos) * 100.0) if amt_total_pos else 0.0
)

print("Payments (positive amounts only):")
print(f"  Count matched: {cnt_matched}/{cnt_total} = {cnt_match_rate:.2f}%")
print(f"  Amount matched: {fmt_money(amt_matched_pos)}/{fmt_money(amt_total_pos)} = {amt_match_rate:.2f}%")
print(f"  Unmatched positive count: {cnt_unmatched}; amount: {fmt_money(amt_unmatched_pos)}")

# Refunds via charter_refunds (assume refund.amount stored as positive numbers for refunds)
if "amount" in ref_cols:
    cur.execute(
        """
        SELECT 
          COUNT(*) AS cnt_total,
          COALESCE(SUM(amount),0) AS amt_total,
          COUNT(CASE WHEN (charter_id IS NOT NULL OR reserve_number IS NOT NULL) THEN 1 END) AS cnt_linked,
          COALESCE(SUM(CASE WHEN (charter_id IS NOT NULL OR reserve_number IS NOT NULL) THEN amount END),0) AS amt_linked,
          COUNT(CASE WHEN (charter_id IS NULL AND reserve_number IS NULL) THEN 1 END) AS cnt_unlinked,
          COALESCE(SUM(CASE WHEN (charter_id IS NULL AND reserve_number IS NULL) THEN amount END),0) AS amt_unlinked
        FROM charter_refunds
        """
    )
    (
        r_cnt_total,
        r_amt_total,
        r_cnt_linked,
        r_amt_linked,
        r_cnt_unlinked,
        r_amt_unlinked,
    ) = cur.fetchone()

    r_cnt_match_rate = (
        r_cnt_linked / r_cnt_total * 100.0 if r_cnt_total else 0.0
    )
    r_amt_match_rate = (
        float(r_amt_linked) / float(r_amt_total) * 100.0 if r_amt_total else 0.0
    )

    print("\nRefunds (charter_refunds):")
    print(
        f"  Count linked: {r_cnt_linked}/{r_cnt_total} = {r_cnt_match_rate:.2f}%"
    )
    print(
        f"  Amount linked: {fmt_money(r_amt_linked)}/{fmt_money(r_amt_total)} = {r_amt_match_rate:.2f}%"
    )
    print(
        f"  Unlinked refunds: {r_cnt_unlinked}; amount: {fmt_money(r_amt_unlinked)}"
    )
else:
    print("\nRefunds table charter_refunds has no amount column-skipping refunds analysis.")

# Compare to charter-side paid amounts
char_paid_field = "paid_amount" if "paid_amount" in char_cols else None
if char_paid_field:
    cur.execute(
        f"SELECT COALESCE(SUM({char_paid_field}),0) FROM charters"
    )
    (char_paid_total,) = cur.fetchone()

    # Net comparison: matched payments minus linked refunds vs sum(charters.paid_amount)
    net_from_rows = (amt_matched_pos or 0) - (r_amt_linked or 0)

    print("\nCharter-side vs row-linked totals:")
    print(f"  Sum(charters.paid_amount): {fmt_money(char_paid_total)}")
    print(
        f"  Matched payments (+) minus linked refunds (-): {fmt_money(net_from_rows)}"
    )
    delta = (char_paid_total or 0) - net_from_rows
    print(f"  Delta (charters minus rows): {fmt_money(delta)}")
else:
    print("\ncharters.paid_amount not present-skipping charter-side comparison.")

# Top unmatched payments by amount (positive only)
print("\nTop 20 UNMATCHED positive payments by amount:")
cur.execute(
    f"""
    SELECT COALESCE({amount_field},0) AS amt, payment_id, account_number, reserve_number, charter_id, payment_date, payment_key
    FROM payments
    WHERE {amount_field} > 0 AND NOT ({link_filter})
    ORDER BY {amount_field} DESC NULLS LAST
    LIMIT 20
    """
)
rows = cur.fetchall()
if rows:
    for amt, pid, acct, res, cid, dt, pkey in rows:
        print(
            f"  {fmt_money(amt)} | payment_id={pid} | reserve={res} | charter_id={cid} | date={dt} | key={pkey}"
        )
else:
    print("  (none)")

# Top unlinked refunds by amount
if "amount" in ref_cols:
    print("\nTop 20 UNLINKED refunds by amount:")
    # Tolerate schema differences (notes/memo/description may vary)
    # Prefer selecting only known-safe columns
    cur.execute(
        """
        SELECT amount, id, reserve_number, charter_id, refund_date
        FROM charter_refunds
        WHERE charter_id IS NULL AND reserve_number IS NULL
        ORDER BY amount DESC NULLS LAST
        LIMIT 20
        """
    )
    rows = cur.fetchall()
    if rows:
        for amt, rid, res, cid, dt in rows:
            print(
                f"  {fmt_money(amt)} | refund_id={rid} | reserve={res} | charter_id={cid} | date={dt}"
            )
    else:
        print("  (none)")

cur.close(); conn.close()

print("\n" + "=" * 100)
print("ANALYSIS COMPLETE")
print("=" * 100)
