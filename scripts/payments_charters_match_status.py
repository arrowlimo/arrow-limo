"""
Year-by-year charter-payment matching status (read-only).

Outputs:
- For each year in charters:
  - total_charters
  - charters_with_payment (by reserve_number sum)
  - charters_unpaid (no payment and total_amount_due > 0)
  - paid_vs_sum_mismatch
- For each year in payments:
  - total_payments
  - payments_matched_to_charter (reserve_number exists in charters)
  - payments_unmatched (reserve_number NULL or not in charters)

Writes a markdown summary to reports/ and prints a short console recap.
"""
import os
import sys
import psycopg2
from datetime import datetime


def connect():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )


def table_exists(cur, name: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
          SELECT 1 FROM information_schema.tables
          WHERE table_schema='public' AND table_name=%s
        )
        """,
        (name,)
    )
    return cur.fetchone()[0]


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
    conn = connect()
    cur = conn.cursor()

    if not table_exists(cur, 'charters') or not table_exists(cur, 'payments'):
        print('Required tables not found (charters/payments).')
        sys.exit(2)

    pcols = columns(cur, 'payments')
    amount_col = 'amount' if 'amount' in pcols else ('payment_amount' if 'payment_amount' in pcols else None)
    date_col = None
    for c in ('payment_date', 'created_at', 'last_updated', 'updated_at'):
        if c in pcols:
            date_col = c
            break
    if not amount_col or not date_col:
        print('payments table missing amount/date columns for analysis')
        sys.exit(2)

    # Year set derived from charters.charter_date (fallback to reservation_time)
    ccols = columns(cur, 'charters')
    charter_date_col = 'charter_date' if 'charter_date' in ccols else (
        'reservation_time' if 'reservation_time' in ccols else None
    )
    if not charter_date_col:
        print('charters table missing date column for analysis')
        sys.exit(2)

    # Build payment sums by reserve_number
    cur.execute(
        f"""
        CREATE TEMP VIEW tmp_payment_sums AS
        SELECT reserve_number, ROUND(SUM(COALESCE({amount_col},0))::numeric,2) AS paid
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number
        """
    )

    # Charter-year aggregates
    cur.execute(
        f"""
        WITH c AS (
          SELECT reserve_number,
                 CAST({charter_date_col} AS DATE) AS cdate,
                 EXTRACT(YEAR FROM CAST({charter_date_col} AS DATE))::int AS cyear,
                 ROUND(COALESCE(total_amount_due,0)::numeric,2) AS total_due,
                 ROUND(COALESCE(paid_amount,0)::numeric,2) AS paid_field
          FROM charters
        ),
        j AS (
          SELECT c.cyear,
                 COUNT(*) AS total_charters,
                 COUNT(*) FILTER (WHERE COALESCE(ps.paid,0) > 0) AS charters_with_payment,
                 COUNT(*) FILTER (WHERE COALESCE(ps.paid,0) = 0 AND c.total_due > 0) AS charters_unpaid,
                 COUNT(*) FILTER (WHERE ROUND(COALESCE(ps.paid,0)::numeric,2) <> c.paid_field) AS paid_vs_sum_mismatch
          FROM c
          LEFT JOIN tmp_payment_sums ps ON ps.reserve_number = c.reserve_number
          GROUP BY c.cyear
        )
        SELECT * FROM j ORDER BY cyear
        """
    )
    charter_rows = cur.fetchall()

    # Payment-year aggregates
    cur.execute(
        f"""
        WITH p AS (
          SELECT reserve_number,
                 CAST({date_col} AS DATE) AS pdate,
                 EXTRACT(YEAR FROM CAST({date_col} AS DATE))::int AS pyear
          FROM payments
        ),
        j AS (
          SELECT p.pyear,
                 COUNT(*) AS total_payments,
                 COUNT(*) FILTER (WHERE p.reserve_number IS NOT NULL) AS payments_with_reserve,
                 COUNT(*) FILTER (
                   WHERE p.reserve_number IS NULL OR NOT EXISTS (
                     SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
                   )
                 ) AS payments_unmatched
          FROM p
          GROUP BY p.pyear
        )
        SELECT * FROM j ORDER BY pyear
        """
    )
    payment_rows = cur.fetchall()

    # Summary counts
    cur.execute(
        """
        SELECT COUNT(*) FROM payments p
        WHERE p.reserve_number IS NOT NULL AND NOT EXISTS (
          SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
        )
        """
    )
    total_unmatched_payments = cur.fetchone()[0]

    # Emit report
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_dir = os.path.join(os.path.dirname(__file__), '..', 'reports')
    report_dir = os.path.abspath(report_dir)
    os.makedirs(report_dir, exist_ok=True)
    path = os.path.join(report_dir, f'payments_charters_match_status_{ts}.md')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('# Charter-Payment Matching Status (Yearly)\n\n')
        f.write('## Charters by Year\n')
        f.write('year | total_charters | with_payment | unpaid | paid_vs_sum_mismatch\n')
        for r in charter_rows:
            year, total, withpay, unpaid, mismatch = r
            f.write(f"{year} | {total} | {withpay} | {unpaid} | {mismatch}\n")
        f.write('\n## Payments by Year\n')
        f.write('year | total_payments | with_reserve | unmatched\n')
        for r in payment_rows:
            year, total, withres, unmatched = r
            f.write(f"{year} | {total} | {withres} | {unmatched}\n")
        f.write(f"\nTotal unmatched payments (reserve_number not in charters): {total_unmatched_payments}\n")

    print('Year-by-year status written to:', path)

    cur.close(); conn.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Failed: {e}", file=sys.stderr)
        sys.exit(2)
