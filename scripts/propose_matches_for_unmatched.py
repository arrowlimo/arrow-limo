"""
Propose matches for unmatched payments (pre-2025) without writing.

Strategy:
- Take payments with NULL reserve_number or reserve_number not in charters.
- For each, find charters within ±7 days of payment_date whose remaining balance or total_due equals the abs(payment amount).
- Output proposals to CSV with confidence score.
"""
import os
import sys
import csv
from datetime import timedelta
import psycopg2


def connect():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***'),
    )


def table_exists(cur, name: str) -> bool:
    cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s)", (name,))
    return cur.fetchone()[0]


def columns(cur, table: str):
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position", (table,))
    return [r[0] for r in cur.fetchall()]


def main():
    conn = connect()
    cur = conn.cursor()

    if not table_exists(cur, 'charters') or not table_exists(cur, 'payments'):
        print('Required tables not found.')
        sys.exit(2)

    pcols = columns(cur, 'payments')
    amount_col = 'amount' if 'amount' in pcols else ('payment_amount' if 'payment_amount' in pcols else None)
    date_col = None
    for c in ('payment_date', 'created_at', 'last_updated', 'updated_at'):
        if c in pcols:
            date_col = c
            break
    if not amount_col or not date_col:
        print('payments missing amount/date columns.')
        sys.exit(2)

    # Build charter payment sums to compute current balances reliably
    cur.execute(
        f"""
        CREATE TEMP VIEW tmp_ps AS
        SELECT reserve_number, ROUND(SUM(COALESCE({amount_col},0))::numeric,2) AS paid
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number
        """
    )

    # Pull unmatched payments pre-2025
    cur.execute(
        f"""
        SELECT payment_id, COALESCE({amount_col},0) AS amount, CAST({date_col} AS DATE) AS pdate
        FROM payments p
        WHERE CAST({date_col} AS DATE) < DATE '2025-01-01'
          AND (p.reserve_number IS NULL OR NOT EXISTS (
                SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
              ))
        ORDER BY pdate
        """
    )
    unmatched = cur.fetchall()

    proposals = []
    for pid, amt, pdate in unmatched:
        target = abs(float(amt))
        # Query charters in a 7-day window
        cur.execute(
            """
                        WITH c AS (
                            SELECT ch.reserve_number AS reserve_number,
                                         CAST(ch.charter_date AS DATE) AS cdate,
                                         ROUND(COALESCE(ch.total_amount_due,0)::numeric,2) AS total_due,
                                         COALESCE(ps.paid,0) AS paid_sum,
                                         ROUND(COALESCE(ch.total_amount_due,0)::numeric,2) - COALESCE(ps.paid,0) AS remaining
                            FROM charters ch
                            LEFT JOIN tmp_ps ps ON ps.reserve_number = ch.reserve_number
                        )
            SELECT reserve_number, cdate, total_due, paid_sum, remaining
            FROM c
            WHERE cdate BETWEEN %s - INTERVAL '7 day' AND %s + INTERVAL '7 day'
              AND (remaining = %s OR total_due = %s)
            ORDER BY ABS(remaining - %s) ASC, ABS(total_due - %s) ASC
            LIMIT 5
            """,
            (pdate, pdate, target, target, target, target)
        )
        for rn, cdate, total_due, paid_sum, remaining in cur.fetchall():
            confidence = 100
            proposals.append([pid, pdate, amt, rn, cdate, total_due, paid_sum, remaining, confidence])

    report_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'reports'))
    os.makedirs(report_dir, exist_ok=True)
    path = os.path.join(report_dir, 'proposed_matches_for_unmatched_pre2025.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['payment_id','payment_date','amount','reserve_number','charter_date','total_due','paid_sum','remaining','confidence'])
        w.writerows(proposals)

    print('Proposals written:', path)
    print('Unmatched payments analyzed:', len(unmatched))
    print('Proposed links:', len(proposals))

    cur.close(); conn.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Failed: {e}", file=sys.stderr)
        sys.exit(2)
