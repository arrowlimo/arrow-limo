"""
Spot-check 10 charters affected by the negative payment deletion to verify
paid_amount and balance correctness.

Sources:
- Takes payment_id list from reports/reclassify_negative_payments_plan_pre2025.csv
- Samples up to 10 unique reserve_numbers and compares:
  - charters.paid_amount vs SUM(payments.amount) for that reserve_number
  - charters.balance == total_amount_due - paid_amount

Outputs a Markdown report in reports/.
"""
import os
import csv
import random
from datetime import datetime
import psycopg2


REPORTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'reports'))
PLAN_CSV = os.path.join(REPORTS_DIR, 'reclassify_negative_payments_plan_pre2025.csv')


def connect():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )


def main():
    if not os.path.exists(PLAN_CSV):
        print(f"Plan CSV not found: {PLAN_CSV}")
        return

    targets = []
    with open(PLAN_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rn = row.get('reserve_number')
            if rn:
                targets.append(rn)

    unique_rns = sorted(set(targets))
    if not unique_rns:
        print("No reserve_numbers found in plan CSV.")
        return

    sample = unique_rns[:10] if len(unique_rns) <= 10 else random.sample(unique_rns, 10)

    conn = connect(); cur = conn.cursor()
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_md = os.path.join(REPORTS_DIR, f'spotcheck_charters_after_negative_delete_{ts}.md')

    with open(out_md, 'w', encoding='utf-8') as f:
        f.write(f"# Spot-check: Charters After Negative Payment Deletion\n\n")
        f.write(f"Generated: {ts}\n\n")
        f.write("reserve_number | total_due | paid_in_charters | sum_payments | balance | expected_balance | ok_paid | ok_balance\n")
        f.write("---|---:|---:|---:|---:|---:|---|---\n")

        for rn in sample:
            # Get charter amounts
            cur.execute(
                """
                SELECT ROUND(COALESCE(total_amount_due,0)::numeric,2) AS total_due,
                       ROUND(COALESCE(paid_amount,0)::numeric,2) AS paid_amt,
                       ROUND(COALESCE(balance,0)::numeric,2) AS balance
                FROM charters WHERE reserve_number = %s
                """,
                (rn,)
            )
            row = cur.fetchone()
            if not row:
                continue
            total_due, paid_amt, balance = row

            # Sum payments now present
            cur.execute(
                """
                SELECT ROUND(COALESCE(SUM(COALESCE(amount,0)),0)::numeric,2) AS sum_amt
                FROM payments WHERE reserve_number = %s
                """,
                (rn,)
            )
            sum_payments = cur.fetchone()[0]

            expected_balance = round((total_due or 0) - (sum_payments or 0), 2)
            ok_paid = (paid_amt == sum_payments)
            ok_balance = (balance == expected_balance)

            f.write(f"{rn}|{total_due}|{paid_amt}|{sum_payments}|{balance}|{expected_balance}|{ok_paid}|{ok_balance}\n")

    cur.close(); conn.close()
    print(f"Spot-check report written: {out_md}")


if __name__ == '__main__':
    main()
