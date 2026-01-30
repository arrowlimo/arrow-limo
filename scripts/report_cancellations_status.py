# Report cancellation status and financials for provided reserve_numbers.
#
# Usage:
#   python -X utf8 scripts/report_cancellations_status.py --reserves 019661,019656,...
#
# Outputs a concise console report and writes a CSV/MD to reports/ for audit.
# No writes performed.
import os
import sys
import csv
import argparse
from datetime import datetime
import psycopg2


def connect():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )


def columns(cur, table: str):
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position
        """,
        (table,)
    )
    return [r[0] for r in cur.fetchall()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--reserves', required=True, help='Comma-separated list of 6-digit reserve_numbers')
    args = ap.parse_args()

    reserves = [r.strip() for r in args.reserves.split(',') if r.strip()]
    if not reserves:
        print('No reserves provided.')
        sys.exit(2)

    conn = connect(); cur = conn.cursor()

    # Determine payments amount column
    pcols = columns(cur, 'payments')
    amount_col = 'amount' if 'amount' in pcols else ('payment_amount' if 'payment_amount' in pcols else None)
    if not amount_col:
        print('payments amount column not found')
        sys.exit(2)

    # Build temp sums and select by comparing reserve_number as text (robust to type/storage)
    cur.execute(
        f"""
        WITH ps AS (
            SELECT reserve_number::text AS reserve_text,
                   ROUND(SUM(COALESCE({amount_col},0))::numeric,2) AS paid
            FROM payments
            WHERE reserve_number::text = ANY(%s)
            GROUP BY reserve_text
        ),
        cs AS (
            SELECT reserve_number::text AS reserve_text,
                   ROUND(SUM(COALESCE(amount,0))::numeric,2) AS charges
            FROM charter_charges
            WHERE reserve_number::text = ANY(%s)
            GROUP BY reserve_text
        )
        SELECT c.reserve_number,
               CAST(c.charter_date AS DATE) AS charter_date,
               COALESCE(c.cancelled, FALSE) AS cancelled,
               ROUND(COALESCE(c.total_amount_due,0)::numeric,2) AS total_due,
               COALESCE(ps.paid,0) AS paid_sum,
               ROUND(COALESCE(c.balance,0)::numeric,2) AS balance,
               COALESCE(cs.charges,0) AS charges_sum,
               COALESCE(c.booking_status, '') AS booking_status,
               COALESCE(c.status, '') AS status
        FROM charters c
        LEFT JOIN ps ON ps.reserve_text = c.reserve_number::text
        LEFT JOIN cs ON cs.reserve_text = c.reserve_number::text
        WHERE c.reserve_number::text = ANY(%s)
        ORDER BY c.reserve_number
        """,
        (reserves, reserves, reserves)
    )
    rows = cur.fetchall()

    if not rows:
        print('No matching charters found for provided reserve_numbers.')
        sys.exit(0)

    reports_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'reports'))
    os.makedirs(reports_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = os.path.join(reports_dir, f'cancellation_status_{ts}.csv')
    md_path = os.path.join(reports_dir, f'cancellation_status_{ts}.md')

    # Console summary
    print('reserve | date | cancelled | total_due | charges | paid | balance | booking_status | status')
    for rn, cdate, cancelled, total_due, paid_sum, balance, charges_sum, bstat, stat in rows:
        print(f"{rn} | {cdate} | {cancelled} | {total_due} | {charges_sum} | {paid_sum} | {balance} | {bstat} | {stat}")

    # Write CSV
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['reserve_number','charter_date','cancelled','total_due','charges_sum','paid_sum','balance','booking_status','status'])
        for rn, cdate, cancelled, total_due, paid_sum, balance, charges_sum, bstat, stat in rows:
            w.writerow([rn, cdate, cancelled, total_due, charges_sum, paid_sum, balance, bstat, stat])

    # Write MD
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('# Cancellation Status Report`n`n')
        f.write('| reserve_number | charter_date | cancelled | total_due | charges_sum | paid_sum | balance | booking_status | status |`n')
        f.write('|---|---|---|---:|---:|---:|---:|---|---|`n')
        for rn, cdate, cancelled, total_due, paid_sum, balance, charges_sum, bstat, stat in rows:
            f.write(f"|{rn}|{cdate}|{cancelled}|{total_due}|{charges_sum}|{paid_sum}|{balance}|{bstat}|{stat}|`n")

    print(f"`nReport written:`n - {csv_path}`n - {md_path}")

    cur.close(); conn.close()


if __name__ == '__main__':
    main()
