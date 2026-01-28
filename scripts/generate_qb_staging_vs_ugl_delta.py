"""
Generate a delta report between qb_transactions_staging and unified_general_ledger (UGL).

Heuristic match:
- Join on txn_date and amount equal to either debit_amount or credit_amount (within a small tolerance).
- When UGL is absent for a staging row, count it as "missing_in_ugl".

Outputs: reports/qb_staging_vs_ugl_delta.md

Notes:
- qb_transactions_staging.amount is best-effort; some lines may be non-transaction XML lines.
- This gives an initial signal of gaps to prioritize by year.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict
import psycopg2


ROOT = Path('l:/limo')
OUT = ROOT / 'reports' / 'qb_staging_vs_ugl_delta.md'


def get_db_connection():
    import os
    host = os.getenv('DB_HOST', 'localhost')
    dbname = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '***REMOVED***')
    return psycopg2.connect(host=host, dbname=dbname, user=user, password=password)


def table_exists(cur, name: str) -> bool:
    cur.execute("""
        SELECT EXISTS (
          SELECT 1 FROM information_schema.tables
          WHERE table_schema='public' AND table_name=%s
        )
    """, (name,))
    return bool(cur.fetchone()[0])


def main():
    conn = get_db_connection(); cur = conn.cursor()

    if not table_exists(cur, 'qb_transactions_staging'):
        OUT.write_text('# Delta report\n\nNo qb_transactions_staging table found.\n', encoding='utf-8')
        return

    # Build a temporary table of UGL signatures by date and amount
    ugl_exists = table_exists(cur, 'unified_general_ledger')
    if ugl_exists:
        cur.execute("DROP TABLE IF EXISTS tmp_ugl_signatures;")
        cur.execute(
            """
            CREATE TEMP TABLE tmp_ugl_signatures AS
            SELECT
              DATE(transaction_date) AS d,
              ROUND(COALESCE(debit_amount,0)::numeric, 2) AS debit,
              ROUND(COALESCE(credit_amount,0)::numeric, 2) AS credit
            FROM unified_general_ledger
            WHERE transaction_date IS NOT NULL;
            CREATE INDEX ON tmp_ugl_signatures (d, debit);
            CREATE INDEX ON tmp_ugl_signatures (d, credit);
            """
        )
        conn.commit()

        # Per-year counts in staging (any date)
        cur.execute(
                """
                SELECT EXTRACT(YEAR FROM txn_date)::int AS y, COUNT(*)
                FROM qb_transactions_staging
                WHERE txn_date IS NOT NULL
                GROUP BY 1 ORDER BY 1
                """
        )
        by_year_any = cur.fetchall()

        # Per-year counts in staging (date and amount)
        cur.execute(
                """
                WITH base AS (
                    SELECT EXTRACT(YEAR FROM txn_date)::int AS y, txn_date::date AS d,
                                 ROUND(COALESCE(amount,0)::numeric, 2) AS amt
                    FROM qb_transactions_staging
                    WHERE txn_date IS NOT NULL AND amount IS NOT NULL
                )
                SELECT y, COUNT(*) FROM base GROUP BY y ORDER BY y
                """
        )
        by_year_with_amt = cur.fetchall()

    missing_by_year: Dict[int, int] = {}
    if ugl_exists:
        cur.execute(
            """
            WITH base AS (
              SELECT EXTRACT(YEAR FROM txn_date)::int AS y, txn_date::date AS d,
                     ROUND(COALESCE(amount,0)::numeric, 2) AS amt
              FROM qb_transactions_staging
              WHERE txn_date IS NOT NULL AND amount IS NOT NULL
            ),
            matched AS (
              SELECT b.*
              FROM base b
              LEFT JOIN tmp_ugl_signatures u
                ON u.d = b.d AND (u.debit = b.amt OR u.credit = b.amt)
            )
            SELECT y, COUNT(*) FILTER (WHERE debit IS NULL AND credit IS NULL) AS missing
            FROM (
              SELECT m.y, m.d, m.amt, u.debit, u.credit
              FROM matched m
              LEFT JOIN tmp_ugl_signatures u
                ON u.d = m.d AND (u.debit = m.amt OR u.credit = m.amt)
            ) z
            GROUP BY y
            ORDER BY y
            """
        )
        for y, c in cur.fetchall():
            missing_by_year[int(y)] = int(c)

    # Write report
    lines = ['# QB Staging vs UGL - Delta by Year', '']
    lines.append('This is a heuristic comparison (date + exact amount match on debit or credit).')
    lines.append('Some staging lines may be non-transaction XML lines and will show as missing.\n')

    lines.append('## Staging counts by year (any date)')
    for y, c in by_year_any:
        lines.append(f'- {int(y)}: {int(c):,}')
    lines.append('')
    lines.append('## Staging counts by year (date + amount parsed)')
    if by_year_with_amt:
        for y, c in by_year_with_amt:
            lines.append(f'- {int(y)}: {int(c):,}')
    else:
        lines.append('- None')
    lines.append('')

    if ugl_exists:
        lines.append('## Missing in UGL (by year)')
        if missing_by_year:
            for y in sorted(missing_by_year.keys()):
                lines.append(f'- {y}: {missing_by_year[y]:,}')
        else:
            lines.append('- None')
    else:
        lines.append('UGL not found; skipping missing-in-UGL analysis.')

    OUT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'[OK] Wrote delta report: {OUT}')

    cur.close(); conn.close()


if __name__ == '__main__':
    main()
