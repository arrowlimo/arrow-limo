"""
Comprehensive, read-only integrity verification for almsdata.

Checks:
- Duplicate payments by (reserve_number, amount, date-only)
- Negative payments remaining (should be 0)
- Unmatched payments (reserve_number not in charters)
- Charters total_amount_due vs SUM(charter_charges.amount)
- Charters paid_amount vs SUM(payments.amount by reserve_number)
- Charters balance = total_amount_due - paid_sum

Outputs concise console summary and writes a markdown report to reports/.
No writes to the database.
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


def safe_count(cur, sql: str):
    cur.execute(sql)
    return cur.fetchone()[0]


def main():
    conn = connect()
    cur = conn.cursor()

    has_payments = table_exists(cur, 'payments')
    has_charters = table_exists(cur, 'charters')
    has_charges = table_exists(cur, 'charter_charges')

    pay_cols = columns(cur, 'payments') if has_payments else []
    char_cols = columns(cur, 'charters') if has_charters else []
    chg_cols = columns(cur, 'charter_charges') if has_charges else []

    amount_col = 'amount' if 'amount' in pay_cols else ('payment_amount' if 'payment_amount' in pay_cols else None)
    date_col = None
    for cand in ('payment_date', 'created_at', 'last_updated', 'updated_at'):
        if cand in pay_cols:
            date_col = cand
            break

    results = []

    # 1) Duplicate payments by (reserve_number, amount, date-only)
    if has_payments and amount_col and date_col:
        cur.execute(
            f"""
            SELECT COUNT(*) FROM (
                SELECT reserve_number, {amount_col}, CAST({date_col} AS DATE) AS d, COUNT(*)
                FROM payments
                WHERE reserve_number IS NOT NULL
                GROUP BY reserve_number, {amount_col}, CAST({date_col} AS DATE)
                HAVING COUNT(*) > 1
            ) s
            """
        )
        dup_count = cur.fetchone()[0]
        results.append(("duplicate_payments", dup_count))
    else:
        results.append(("duplicate_payments", 'n/a'))

    # 2) Negative payments remaining
    neg_payments = 'n/a'
    if has_payments and amount_col:
        cur.execute(f"SELECT COUNT(*) FROM payments WHERE {amount_col} < 0")
        neg_payments = cur.fetchone()[0]
    results.append(("negative_payments", neg_payments))

    # 3) Unmatched payments (reserve_number not in charters)
    unmatched = 'n/a'
    if has_payments and has_charters:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM payments p
            WHERE p.reserve_number IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
              )
            """
        )
        unmatched = cur.fetchone()[0]
    results.append(("unmatched_payments", unmatched))

    # 4) Charters total_amount_due vs SUM(charter_charges.amount)
    tot_mismatch = 'n/a'
    sample_totals = []
    if has_charters:
        # Build join strategy: prefer charter_id if present in charter_charges, else reserve_number if available
        join_clause = None
        if 'charter_id' in char_cols and 'charter_id' in chg_cols:
            join_clause = 'cc.charter_id = c.charter_id'
        elif 'reserve_number' in char_cols and 'reserve_number' in chg_cols:
            join_clause = 'cc.reserve_number = c.reserve_number'
        if join_clause:
            cur.execute(
                f"""
                SELECT COUNT(*) FROM (
                    SELECT c.reserve_number,
                           ROUND(COALESCE(SUM(cc.amount),0)::numeric,2) AS charges_sum,
                           ROUND(COALESCE(c.total_amount_due,0)::numeric,2) AS total_due
                    FROM charters c
                    LEFT JOIN charter_charges cc ON {join_clause}
                    GROUP BY c.reserve_number, c.total_amount_due
                    HAVING ROUND(COALESCE(SUM(cc.amount),0)::numeric,2) <> ROUND(COALESCE(c.total_amount_due,0)::numeric,2)
                ) s
                """
            )
            tot_mismatch = cur.fetchone()[0]
            # sample 10
            cur.execute(
                f"""
                SELECT c.reserve_number,
                       ROUND(COALESCE(SUM(cc.amount),0)::numeric,2) AS charges_sum,
                       ROUND(COALESCE(c.total_amount_due,0)::numeric,2) AS total_due
                FROM charters c
                LEFT JOIN charter_charges cc ON {join_clause}
                GROUP BY c.reserve_number, c.total_amount_due
                HAVING ROUND(COALESCE(SUM(cc.amount),0)::numeric,2) <> ROUND(COALESCE(c.total_amount_due,0)::numeric,2)
                ORDER BY ABS(ROUND(COALESCE(SUM(cc.amount),0)::numeric,2) - ROUND(COALESCE(c.total_amount_due,0)::numeric,2)) DESC
                LIMIT 10
                """
            )
            sample_totals = cur.fetchall()
    results.append(("charter_total_vs_charges_mismatch", tot_mismatch))

    # 5) Charters paid_amount vs SUM(payments by reserve_number)
    paid_mismatch = 'n/a'
    sample_paid = []
    if has_charters and has_payments and amount_col:
        cur.execute(
            f"""
            WITH payment_sums AS (
              SELECT reserve_number, ROUND(SUM(COALESCE({amount_col},0))::numeric,2) AS paid
              FROM payments
              WHERE reserve_number IS NOT NULL
              GROUP BY reserve_number
            )
            SELECT COUNT(*) FROM (
              SELECT c.reserve_number,
                     ps.paid AS paid_sum,
                     ROUND(COALESCE(c.paid_amount,0)::numeric,2) AS paid_field
              FROM charters c
              LEFT JOIN payment_sums ps ON ps.reserve_number = c.reserve_number
              WHERE ROUND(COALESCE(ps.paid,0)::numeric,2) <> ROUND(COALESCE(c.paid_amount,0)::numeric,2)
            ) s
            """
        )
        paid_mismatch = cur.fetchone()[0]
        # sample 10
        cur.execute(
            f"""
            WITH payment_sums AS (
              SELECT reserve_number, ROUND(SUM(COALESCE({amount_col},0))::numeric,2) AS paid
              FROM payments
              WHERE reserve_number IS NOT NULL
              GROUP BY reserve_number
            )
            SELECT c.reserve_number,
                   ps.paid AS paid_sum,
                   ROUND(COALESCE(c.paid_amount,0)::numeric,2) AS paid_field
            FROM charters c
            LEFT JOIN payment_sums ps ON ps.reserve_number = c.reserve_number
            WHERE ROUND(COALESCE(ps.paid,0)::numeric,2) <> ROUND(COALESCE(c.paid_amount,0)::numeric,2)
            ORDER BY ABS(ROUND(COALESCE(ps.paid,0)::numeric,2) - ROUND(COALESCE(c.paid_amount,0)::numeric,2)) DESC
            LIMIT 10
            """
        )
        sample_paid = cur.fetchall()
    results.append(("charter_paid_vs_sum_payments_mismatch", paid_mismatch))

    # 6) Balance correctness: balance = total_amount_due - sum(payments)
    bal_mismatch = 'n/a'
    sample_bal = []
    if has_charters and has_payments and amount_col:
        cur.execute(
            f"""
            WITH payment_sums AS (
              SELECT reserve_number, ROUND(SUM(COALESCE({amount_col},0))::numeric,2) AS paid
              FROM payments
              WHERE reserve_number IS NOT NULL
              GROUP BY reserve_number
            )
            SELECT COUNT(*) FROM (
              SELECT c.reserve_number,
                     ROUND(COALESCE(c.total_amount_due,0)::numeric,2) - ROUND(COALESCE(ps.paid,0)::numeric,2) AS expected_balance,
                     ROUND(COALESCE(c.balance,0)::numeric,2) AS balance_field
              FROM charters c
              LEFT JOIN payment_sums ps ON ps.reserve_number = c.reserve_number
              WHERE (ROUND(COALESCE(c.total_amount_due,0)::numeric,2) - ROUND(COALESCE(ps.paid,0)::numeric,2))
                    <> ROUND(COALESCE(c.balance,0)::numeric,2)
            ) s
            """
        )
        bal_mismatch = cur.fetchone()[0]
        cur.execute(
            f"""
            WITH payment_sums AS (
              SELECT reserve_number, ROUND(SUM(COALESCE({amount_col},0))::numeric,2) AS paid
              FROM payments
              WHERE reserve_number IS NOT NULL
              GROUP BY reserve_number
            )
            SELECT c.reserve_number,
                   ROUND(COALESCE(c.total_amount_due,0)::numeric,2) AS total_due,
                   COALESCE(ps.paid,0) AS paid_sum,
                   ROUND(COALESCE(c.balance,0)::numeric,2) AS balance_field,
                   (ROUND(COALESCE(c.total_amount_due,0)::numeric,2) - COALESCE(ps.paid,0)) AS expected_balance
            FROM charters c
            LEFT JOIN payment_sums ps ON ps.reserve_number = c.reserve_number
            WHERE (ROUND(COALESCE(c.total_amount_due,0)::numeric,2) - ROUND(COALESCE(ps.paid,0)::numeric,2))
                  <> ROUND(COALESCE(c.balance,0)::numeric,2)
            ORDER BY ABS((ROUND(COALESCE(c.total_amount_due,0)::numeric,2) - COALESCE(ps.paid,0)) - ROUND(COALESCE(c.balance,0)::numeric,2)) DESC
            LIMIT 10
            """
        )
        sample_bal = cur.fetchall()
    results.append(("charter_balance_mismatch", bal_mismatch))

    # Console summary
    print("Integrity Verification Summary:")
    for k, v in results:
        print(f"- {k}: {v}")

    # Write markdown report
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_dir = os.path.join(os.path.dirname(__file__), '..', 'reports')
    report_dir = os.path.abspath(report_dir)
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f'almsdata_verification_{ts}.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('# ALMS Data Integrity Verification\n\n')
        for k, v in results:
            f.write(f"- {k}: {v}\n")
        if sample_totals:
            f.write('\n## Sample charter total vs charges mismatches (top 10)\n')
            f.write('reserve_number | charges_sum | total_due\n')
            for rn, s, d in sample_totals:
                f.write(f"{rn} | {s} | {d}\n")
        if sample_paid:
            f.write('\n## Sample charter paid vs sum(payments) mismatches (top 10)\n')
            f.write('reserve_number | paid_sum | paid_field\n')
            for rn, ps, pf in sample_paid:
                f.write(f"{rn} | {ps} | {pf}\n")
        if sample_bal:
            f.write('\n## Sample charter balance mismatches (top 10)\n')
            f.write('reserve_number | total_due | paid_sum | balance_field | expected_balance\n')
            for rn, td, ps, bf, eb in sample_bal:
                f.write(f"{rn} | {td} | {ps} | {bf} | {eb}\n")

    print(f"\nReport written: {report_path}")

    cur.close(); conn.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Verification failed: {e}", file=sys.stderr)
        sys.exit(2)
