"""
Export unmatched positive payments (no reserve_number/charter_id) and unlinked refunds
for manual review.

Outputs CSVs in reports/:
- reports/unmatched_positive_payments.csv
- reports/unlinked_refunds.csv

Filters:
- Payments: amount/payment_amount > 0 and no link fields
- Refunds: charter_refunds where both charter_id and reserve_number are NULL
- Only top N by amount if --limit is provided (default: all)
"""
import argparse
import csv
import os
import psycopg2


def get_conn():
    return psycopg2.connect(
        host="localhost", database="almsdata", user="postgres", password="***REMOVED***"
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
    raise RuntimeError("payments table missing amount/payment_amount column")


def main(limit: int | None):
    os.makedirs("reports", exist_ok=True)
    conn = get_conn(); cur = conn.cursor()

    pay_cols = columns(cur, "payments")
    ref_cols = columns(cur, "charter_refunds")
    amount_field = pick_payment_amount_field(pay_cols)

    link_parts = []
    if "reserve_number" in pay_cols:
        link_parts.append("reserve_number IS NOT NULL")
    if "charter_id" in pay_cols:
        link_parts.append("charter_id IS NOT NULL")
    link_filter = " OR ".join(link_parts) if link_parts else "FALSE"

    # Unmatched positive payments
    cur.execute(
        f"""
        SELECT payment_id, {amount_field} AS amount, account_number, reserve_number, charter_id, payment_date, payment_key, payment_method
        FROM payments
        WHERE {amount_field} > 0 AND NOT ({link_filter})
        ORDER BY {amount_field} DESC NULLS LAST
        {f'LIMIT {limit}' if limit else ''}
        """
    )
    pay_rows = cur.fetchall()
    with open("reports/unmatched_positive_payments.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["payment_id", "amount", "account_number", "reserve_number", "charter_id", "payment_date", "payment_key", "payment_method"])
        for r in pay_rows:
            w.writerow(r)

    # Unlinked refunds
    if "amount" in ref_cols:
        cur.execute(
            """
            SELECT id, amount, reserve_number, charter_id, refund_date
            FROM charter_refunds
            WHERE charter_id IS NULL AND reserve_number IS NULL
            ORDER BY amount DESC NULLS LAST
            """ + (f" LIMIT {limit}" if limit else "")
        )
        ref_rows = cur.fetchall()
        with open("reports/unlinked_refunds.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["refund_id", "amount", "reserve_number", "charter_id", "refund_date"])
            for r in ref_rows:
                w.writerow(r)

    cur.close(); conn.close()
    print(f"Exported {len(pay_rows)} unmatched payments and {len(ref_rows) if 'ref_rows' in locals() else 0} unlinked refunds.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="Optional limit of rows to export per file")
    args = ap.parse_args()
    main(args.limit)
