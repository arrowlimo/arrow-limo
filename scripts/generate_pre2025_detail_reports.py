"""
Generate read-only drilldown reports for pre-2025 data:
- Unmatched payments (reserve_number NULL or not in charters)
- Negative payments (amount < 0)
- Charter mismatches (paid vs sum(payments), balance correctness, totals vs charges)

Outputs CSV + Markdown into reports/.
No database writes.
"""
import os
import sys
import csv
import psycopg2
from datetime import datetime, date

CUTOFF = date(2025, 1, 1)


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


def ensure_reports_dir():
    report_dir = os.path.join(os.path.dirname(__file__), '..', 'reports')
    report_dir = os.path.abspath(report_dir)
    os.makedirs(report_dir, exist_ok=True)
    return report_dir


def main():
    conn = connect()
    cur = conn.cursor()

    if not table_exists(cur, 'charters') or not table_exists(cur, 'payments'):
        print('Required tables not found (charters/payments).', file=sys.stderr)
        sys.exit(2)

    pcols = columns(cur, 'payments')
    ccols = columns(cur, 'charters')
    chg_exists = table_exists(cur, 'charter_charges')
    chg_cols = columns(cur, 'charter_charges') if chg_exists else []

    amount_col = 'amount' if 'amount' in pcols else ('payment_amount' if 'payment_amount' in pcols else None)
    date_col = None
    for c in ('payment_date', 'created_at', 'last_updated', 'updated_at'):
        if c in pcols:
            date_col = c
            break
    charter_date_col = 'charter_date' if 'charter_date' in ccols else (
        'reservation_time' if 'reservation_time' in ccols else None
    )
    if not amount_col or not date_col or not charter_date_col:
        print('Missing critical columns for analysis.', file=sys.stderr)
        sys.exit(2)

    # Build payment_sums pre-2025
    cur.execute(
        f"""
        CREATE TEMP VIEW tmp_payment_sums_pre AS
        SELECT reserve_number, ROUND(SUM(COALESCE({amount_col},0))::numeric,2) AS paid
        FROM payments
        WHERE reserve_number IS NOT NULL
          AND CAST({date_col} AS DATE) < %s
        GROUP BY reserve_number
        """,
        (CUTOFF,)
    )

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_dir = ensure_reports_dir()
    md_path = os.path.join(report_dir, f'pre2025_drilldown_{ts}.md')

    # 1) Unmatched payments (pre-2025)
    cur.execute(
        f"""
        SELECT p.payment_id,
               p.reserve_number,
               COALESCE({amount_col},0) AS amount,
               CAST({date_col} AS DATE) AS pdate,
               COALESCE(p.payment_key, '') AS payment_key,
               COALESCE(p.payment_method, '') AS payment_method
        FROM payments p
        WHERE CAST({date_col} AS DATE) < %s
          AND (
                p.reserve_number IS NULL OR NOT EXISTS (
                  SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
                )
              )
        ORDER BY pdate DESC, amount DESC
        """,
        (CUTOFF,)
    )
    unmatched_rows = cur.fetchall()
    unmatched_csv = os.path.join(report_dir, f'unmatched_payments_pre2025_{ts}.csv')
    with open(unmatched_csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['payment_id','reserve_number','amount','payment_date','payment_key','payment_method'])
        w.writerows(unmatched_rows)

    # 2) Negative payments (pre-2025)
    cur.execute(
        f"""
        SELECT p.payment_id,
               p.reserve_number,
               COALESCE({amount_col},0) AS amount,
               CAST({date_col} AS DATE) AS pdate,
               COALESCE(p.payment_key,'') AS payment_key,
               COALESCE(p.payment_method,'') AS payment_method
        FROM payments p
        WHERE CAST({date_col} AS DATE) < %s
          AND COALESCE({amount_col},0) < 0
        ORDER BY amount ASC
        """,
        (CUTOFF,)
    )
    negative_rows = cur.fetchall()
    negative_csv = os.path.join(report_dir, f'negative_payments_pre2025_{ts}.csv')
    with open(negative_csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['payment_id','reserve_number','amount','payment_date','payment_key','payment_method'])
        w.writerows(negative_rows)

    # 3) Charter paid vs sum(payments) mismatches (pre-2025)
    cur.execute(
        f"""
        WITH c AS (
          SELECT reserve_number,
                 CAST({charter_date_col} AS DATE) AS cdate,
                 ROUND(COALESCE(total_amount_due,0)::numeric,2) AS total_due,
                 ROUND(COALESCE(paid_amount,0)::numeric,2) AS paid_field
          FROM charters
          WHERE CAST({charter_date_col} AS DATE) < %s
        )
        SELECT c.reserve_number,
               c.cdate,
               c.total_due,
               c.paid_field,
               COALESCE(ps.paid,0) AS paid_sum,
               (COALESCE(ps.paid,0) - c.paid_field) AS paid_delta
        FROM c
        LEFT JOIN tmp_payment_sums_pre ps ON ps.reserve_number = c.reserve_number
        WHERE ROUND(COALESCE(ps.paid,0)::numeric,2) <> c.paid_field
        ORDER BY ABS(COALESCE(ps.paid,0) - c.paid_field) DESC
        """,
        (CUTOFF,)
    )
    paid_mismatch_rows = cur.fetchall()
    paid_mismatch_csv = os.path.join(report_dir, f'charter_paid_mismatch_pre2025_{ts}.csv')
    with open(paid_mismatch_csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['reserve_number','charter_date','total_due','paid_field','paid_sum','paid_delta'])
        w.writerows(paid_mismatch_rows)

    # 4) Charter balance mismatches (pre-2025)
    cur.execute(
        f"""
        WITH c AS (
          SELECT reserve_number,
                 CAST({charter_date_col} AS DATE) AS cdate,
                 ROUND(COALESCE(total_amount_due,0)::numeric,2) AS total_due,
                 ROUND(COALESCE(balance,0)::numeric,2) AS bal_field
          FROM charters
          WHERE CAST({charter_date_col} AS DATE) < %s
        )
        SELECT c.reserve_number,
               c.cdate,
               c.total_due,
               COALESCE(ps.paid,0) AS paid_sum,
               c.bal_field,
               (c.total_due - COALESCE(ps.paid,0)) AS expected_balance,
               ((c.total_due - COALESCE(ps.paid,0)) - c.bal_field) AS bal_delta
        FROM c
        LEFT JOIN tmp_payment_sums_pre ps ON ps.reserve_number = c.reserve_number
        WHERE (c.total_due - COALESCE(ps.paid,0)) <> c.bal_field
        ORDER BY ABS((c.total_due - COALESCE(ps.paid,0)) - c.bal_field) DESC
        """,
        (CUTOFF,)
    )
    bal_mismatch_rows = cur.fetchall()
    bal_mismatch_csv = os.path.join(report_dir, f'charter_balance_mismatch_pre2025_{ts}.csv')
    with open(bal_mismatch_csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['reserve_number','charter_date','total_due','paid_sum','balance_field','expected_balance','balance_delta'])
        w.writerows(bal_mismatch_rows)

    # 5) Totals vs charges mismatches (pre-2025) if charter_charges available
    totals_vs_charges_csv = None
    totals_vs_charges_count = None
    if chg_exists:
        join_clause = None
        if 'charter_id' in ccols and 'charter_id' in chg_cols:
            join_clause = 'cc.charter_id = c.charter_id'
        elif 'reserve_number' in ccols and 'reserve_number' in chg_cols:
            join_clause = 'cc.reserve_number = c.reserve_number'
        if join_clause:
            cur.execute(
                f"""
                WITH c AS (
                  SELECT * FROM charters WHERE CAST({charter_date_col} AS DATE) < %s
                )
                SELECT c.reserve_number,
                       CAST({charter_date_col} AS DATE) AS cdate,
                       ROUND(COALESCE(c.total_amount_due,0)::numeric,2) AS total_due,
                       ROUND(COALESCE(SUM(cc.amount),0)::numeric,2) AS charges_sum,
                       (ROUND(COALESCE(SUM(cc.amount),0)::numeric,2) - ROUND(COALESCE(c.total_amount_due,0)::numeric,2)) AS delta
                FROM c
                LEFT JOIN charter_charges cc ON {join_clause}
                GROUP BY c.reserve_number, c.{charter_date_col}, c.total_amount_due
                HAVING ROUND(COALESCE(SUM(cc.amount),0)::numeric,2) <> ROUND(COALESCE(c.total_amount_due,0)::numeric,2)
                ORDER BY ABS(ROUND(COALESCE(SUM(cc.amount),0)::numeric,2) - ROUND(COALESCE(c.total_amount_due,0)::numeric,2)) DESC
                """,
                (CUTOFF,)
            )
            rows = cur.fetchall()
            totals_vs_charges_count = len(rows)
            totals_vs_charges_csv = os.path.join(report_dir, f'charter_totals_vs_charges_pre2025_{ts}.csv')
            with open(totals_vs_charges_csv, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(['reserve_number','charter_date','total_due','charges_sum','delta'])
                w.writerows(rows)

    # Markdown rollup
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('# Pre-2025 Drilldown Reports (Read-only)\n\n')
        f.write(f'- Unmatched payments: {len(unmatched_rows)} → {os.path.basename(unmatched_csv)}\n')
        f.write(f'- Negative payments: {len(negative_rows)} → {os.path.basename(negative_csv)}\n')
        f.write(f'- Charter paid vs sum(payments) mismatches: {len(paid_mismatch_rows)} → {os.path.basename(paid_mismatch_csv)}\n')
        f.write(f'- Charter balance mismatches: {len(bal_mismatch_rows)} → {os.path.basename(bal_mismatch_csv)}\n')
        if totals_vs_charges_csv is not None:
            f.write(f'- Charter totals vs charges mismatches: {totals_vs_charges_count} → {os.path.basename(totals_vs_charges_csv)}\n')

    print('Reports written:')
    print('  ', md_path)
    print('  ', unmatched_csv)
    print('  ', negative_csv)
    print('  ', paid_mismatch_csv)
    print('  ', bal_mismatch_csv)
    if totals_vs_charges_csv:
        print('  ', totals_vs_charges_csv)

    cur.close(); conn.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Failed: {e}", file=sys.stderr)
        sys.exit(2)
