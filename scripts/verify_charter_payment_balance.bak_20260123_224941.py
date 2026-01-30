"""
Verify per-charter payment balancing.

For each charter:
- payments_sum = SUM(charter_payments.amount) where charter_payments.charter_id = charters.reserve_number
- refunds_sum  = SUM(charter_refunds.amount) (if table exists) where charter_refunds.charter_id = charters.reserve_number
- net_paid     = payments_sum - refunds_sum
- expected_balance = ROUND(total_amount_due - net_paid, 2)
- Compare to recorded `charters.balance` and flag mismatches

Outputs:
- Summary counts by status (balanced / underpaid / overpaid / within_penny)
- CSV reports under reports/ for mismatches and link inconsistencies

Notes:
- charter_payments is source of truth for amounts; payments table is metadata-only (amounts often NULL)
- We still check linkage consistency between charter_payments -> payments metadata (reserve_number/charter_id)
"""
import os
import csv
import psycopg2


def get_conn():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***",
    )


def table_exists(cur, table_name: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        )
        """,
        (table_name,),
    )
    return cur.fetchone()[0]


def ensure_reports_dir():
    outdir = os.path.join("reports")
    os.makedirs(outdir, exist_ok=True)
    return outdir


def main():
    conn = get_conn()
    cur = conn.cursor()

    print("=" * 100)
    print("VERIFY CHARTER PAYMENT BALANCING")
    print("=" * 100)

    has_refunds = table_exists(cur, "charter_refunds")
    if has_refunds:
        # Verify expected columns
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name='charter_refunds'
            """
        )
        refund_cols = {r[0] for r in cur.fetchall()}
        if not ({'charter_id', 'amount'} <= refund_cols):
            has_refunds = False
            print("Note: charter_refunds exists but missing expected columns; ignoring refunds in computation.")

    # Core aggregation
        cur.execute(
                f"""
        WITH payments AS (
                    SELECT charter_id::text AS reserve_number, COALESCE(SUM(amount),0) AS payments_sum
          FROM charter_payments
          WHERE charter_id IS NOT NULL
          GROUP BY charter_id
        ),
        refunds AS (
                    SELECT charter_id::text AS reserve_number, COALESCE(SUM(amount),0) AS refunds_sum
          FROM {('charter_refunds' if has_refunds else '(SELECT NULL::text AS charter_id, 0::numeric AS amount) x')}
          GROUP BY charter_id
        ),
        totals AS (
          SELECT 
            c.charter_id,
            c.reserve_number,
            COALESCE(c.total_amount_due,0) AS total_due,
            COALESCE(p.payments_sum,0) AS payments_sum,
            COALESCE(r.refunds_sum,0) AS refunds_sum,
            COALESCE(c.paid_amount,0) AS paid_amount,
            COALESCE(c.balance,0) AS recorded_balance
          FROM charters c
                    LEFT JOIN payments p ON p.reserve_number = c.reserve_number::text
                    LEFT JOIN refunds  r ON r.reserve_number = c.reserve_number::text
        )
        SELECT 
          charter_id, reserve_number, total_due, payments_sum, refunds_sum,
          paid_amount, recorded_balance,
          ROUND(payments_sum - refunds_sum, 2) AS net_paid,
          ROUND(total_due - (payments_sum - refunds_sum), 2) AS expected_balance,
          ROUND((total_due - (payments_sum - refunds_sum)) - recorded_balance, 2) AS diff
        FROM totals
        """
    )
    rows = cur.fetchall()

    # Classification
    tolerance = 0.02
    balanced = []
    within_penny = []
    underpaid = []  # expected_balance > recorded_balance (customer owes more)
    overpaid = []   # expected_balance < recorded_balance (we owe customer)

    for (cid, res, total_due, pay_sum, ref_sum, paid_amt, rec_bal, net_paid, exp_bal, diff) in rows:
        # diff = expected_balance - recorded_balance
        if abs(diff) <= 0.00001 and abs(exp_bal) <= tolerance:
            balanced.append((cid, res, total_due, pay_sum, ref_sum, net_paid, exp_bal, rec_bal, diff))
        elif abs(diff) <= tolerance:
            within_penny.append((cid, res, total_due, pay_sum, ref_sum, net_paid, exp_bal, rec_bal, diff))
        elif diff > tolerance:
            # recorded balance is lower than expected; under-collected
            underpaid.append((cid, res, total_due, pay_sum, ref_sum, net_paid, exp_bal, rec_bal, diff))
        else:
            overpaid.append((cid, res, total_due, pay_sum, ref_sum, net_paid, exp_bal, rec_bal, diff))

    print("\nSUMMARY:")
    print("-" * 100)
    print(f"Total charters: {len(rows):,}")
    print(f"Balanced (zero +/- tolerance): {len(balanced):,}")
    print(f"Within $0.02 tolerance: {len(within_penny):,}")
    print(f"Underpaid (owe > 0): {len(underpaid):,}")
    print(f"Overpaid (credit due): {len(overpaid):,}")

    # Link consistency (optional)
    print("\nChecking link consistency (charter_payments -> payments metadata)...")
    cur.execute(
        """
        SELECT 
          c.charter_id,
          c.reserve_number,
          COUNT(*) AS linked,
          SUM(CASE WHEN (p.reserve_number = c.reserve_number OR p.charter_id = c.charter_id) THEN 0 ELSE 1 END) AS inconsistent
        FROM charters c
        JOIN charter_payments cp ON cp.charter_id = c.reserve_number
        LEFT JOIN payments p ON p.payment_id = cp.payment_id
        GROUP BY c.charter_id, c.reserve_number
        """
    )
    link_rows = cur.fetchall()
    inconsistent = [(cid, res, linked, inc) for cid, res, linked, inc in link_rows if inc and inc > 0]
    print(f"Inconsistent links (metadata mismatch): {len(inconsistent):,}")

    outdir = ensure_reports_dir()

    def write_csv(name, data):
        path = os.path.join(outdir, name)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["charter_id","reserve_number","total_due","payments_sum","refunds_sum","net_paid","expected_balance","recorded_balance","difference"])
            for (cid, res, total_due, pay_sum, ref_sum, net_paid, exp_bal, rec_bal, diff) in data:
                w.writerow([cid, res, float(total_due or 0), float(pay_sum or 0), float(ref_sum or 0), float(net_paid or 0), float(exp_bal or 0), float(rec_bal or 0), float(diff or 0)])
        return path

    mismatches = underpaid + overpaid
    mismatches_path = write_csv("charter_balance_mismatches.csv", mismatches)
    write_csv("charter_underpaid.csv", underpaid)
    write_csv("charter_overpaid.csv", overpaid)

    # Link inconsistencies CSV
    link_path = os.path.join(outdir, "charter_link_inconsistencies.csv")
    with open(link_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["charter_id","reserve_number","linked_count","inconsistent_count"])
        for cid, res, linked, inc in inconsistent:
            w.writerow([cid, res, linked, inc])

    # Print top 20 mismatches
    mismatches_sorted = sorted(mismatches, key=lambda r: abs(r[-1]), reverse=True)[:20]
    print("\nTOP 20 MISMATCHES (by absolute difference):")
    print("-" * 100)
    print("Charter  Reserve   Total$     PaidNet$  Expected$  Recorded$  Diff$")
    print("-" * 100)
    for (cid, res, total_due, pay_sum, ref_sum, net_paid, exp_bal, rec_bal, diff) in mismatches_sorted:
        print(f"{cid:7d}  {res:7s}  ${float(total_due or 0):9,.2f}  ${float(net_paid or 0):9,.2f}  ${float(exp_bal or 0):9,.2f}  ${float(rec_bal or 0):9,.2f}  ${float(diff or 0):9,.2f}")

    print("\nReports written:")
    print(f"- {mismatches_path}")
    print(f"- {link_path}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
