#!/usr/bin/env python3
"""
Monthly Banking Reconciliation Report (Schema-aware)
===================================================

Generates:
- Monthly totals (debits, credits, net change, txn count) for a bank account/year
- Monthly category breakdowns (category, debits, credits, txn count)
- Optional details per month (disabled by default for size)

Outputs under: exports/banking/<account>/<year>/
- banking_monthly_summary.csv
- banking_monthly_categories.csv
- (optional) banking_month_YYYY-MM.csv (set --details)

Assumptions:
- Debits = money leaving the account; Credits = money coming in.
- Schema varies; script introspects column names and adapts.

Usage:
  python -X utf8 scripts/generate_banking_reconciliation_report.py --account 1000 --year 2012

Env:
  DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT
"""
from __future__ import annotations

import os
import sys
import csv
import argparse
from datetime import date, datetime
import calendar
import psycopg2

DSN = dict(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REDACTED***'),
    port=int(os.environ.get('DB_PORT', '5432')),
)


def get_columns(conn, table: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s
            """,
            (table,),
        )
        return {r[0] for r in cur.fetchall()}


def pick(colnames: set[str], *options: str) -> str | None:
    for opt in options:
        if opt in colnames:
            return opt
    return None


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def month_range(year: int):
    for m in range(1, 13):
        start = date(year, m, 1)
        end = date(year, m, calendar.monthrange(year, m)[1])
        yield m, start, end


def build_filters(cols: set[str], account: str | None):
    date_col = pick(cols, 'transaction_date', 'trans_date', 'date', 'posting_date') or 'transaction_date'
    debit = pick(cols, 'debit_amount', 'debit')
    credit = pick(cols, 'credit_amount', 'credit')
    category = pick(cols, 'category')
    desc_col = pick(cols, 'description', 'memo', 'vendor_name')
    account_col = pick(cols, 'account_number', 'account', 'account_code')
    balance_col = pick(cols, 'balance')

    if not (debit and credit and date_col):
        raise SystemExit('banking_transactions schema missing debit/credit/date columns')

    where = 'TRUE'
    params = []
    if account and account_col:
        where = f"{account_col} = %s"
        params.append(account)

    return dict(
        date_col=date_col,
        debit=debit,
        credit=credit,
        category=category,
        desc_col=desc_col,
        account_col=account_col,
        balance_col=balance_col,
        where=where,
        params=params,
    )


def monthly_summary(conn, f, year: int, out_summary_csv: str):
    date_col, debit, credit, where, params = f['date_col'], f['debit'], f['credit'], f['where'], f['params']
    sql = f"""
        SELECT
          date_trunc('month', {date_col})::date AS month_start,
          (date_trunc('month', {date_col}) + interval '1 month' - interval '1 day')::date AS month_end,
          COALESCE(SUM({debit}),0) AS total_debits,
          COALESCE(SUM({credit}),0) AS total_credits,
          COUNT(*) AS transactions
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM {date_col}) = %s
          AND {where}
        GROUP BY 1,2
        ORDER BY 1
    """
    with conn.cursor() as cur, open(out_summary_csv, 'w', newline='', encoding='utf-8') as out:
        w = csv.writer(out)
        w.writerow(['period_start', 'period_end', 'total_debits', 'total_credits', 'net_change', 'transactions'])
        cur.execute(sql, [year] + params)
        rows = cur.fetchall()
        for r in rows:
            start, end, deb, cred, tx = r
            net = float(cred or 0) - float(deb or 0)
            w.writerow([start, end, f"{float(deb or 0):.2f}", f"{float(cred or 0):.2f}", f"{net:.2f}", int(tx or 0)])
    return len(rows)


def monthly_categories(conn, f, year: int, out_cat_csv: str):
    date_col, debit, credit, category, where, params = f['date_col'], f['debit'], f['credit'], f['category'], f['where'], f['params']
    cat_expr = category if category else "''"
    sql = f"""
        SELECT
          date_trunc('month', {date_col})::date AS month_start,
          (date_trunc('month', {date_col}) + interval '1 month' - interval '1 day')::date AS month_end,
          COALESCE({cat_expr}, 'uncategorized') AS category,
          COALESCE(SUM({debit}),0) AS total_debits,
          COALESCE(SUM({credit}),0) AS total_credits,
          COUNT(*) AS transactions
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM {date_col}) = %s
          AND {where}
        GROUP BY 1,2,3
        ORDER BY 1, 4 DESC
    """
    with conn.cursor() as cur, open(out_cat_csv, 'w', newline='', encoding='utf-8') as out:
        w = csv.writer(out)
        w.writerow(['period_start', 'period_end', 'category', 'total_debits', 'total_credits', 'net_change', 'transactions'])
        cur.execute(sql, [year] + params)
        rows = cur.fetchall()
        for r in rows:
            start, end, cat, deb, cred, tx = r
            net = float(cred or 0) - float(deb or 0)
            w.writerow([start, end, cat, f"{float(deb or 0):.2f}", f"{float(cred or 0):.2f}", f"{net:.2f}", int(tx or 0)])
        return len(rows)


def monthly_details(conn, f, year: int, outdir: str):
    # Optional detail per month
    date_col, debit, credit, where, params = f['date_col'], f['debit'], f['credit'], f['where'], f['params']
    desc_col = f['desc_col'] or "''"
    account_col = f['account_col'] or "''"
    sql = f"""
        SELECT {date_col}::date AS trans_date,
               {account_col} AS account,
               {desc_col} AS description,
               {debit} AS debit_amount,
               {credit} AS credit_amount
        FROM banking_transactions
        WHERE {date_col} BETWEEN %s AND %s
          AND {where}
        ORDER BY {date_col}
    """
    with conn.cursor() as cur:
        for m, start, end in month_range(year):
            out_csv = os.path.join(outdir, f"banking_month_{start.strftime('%Y-%m')}.csv")
            with open(out_csv, 'w', newline='', encoding='utf-8') as out:
                w = csv.writer(out)
                w.writerow(['date', 'account', 'description', 'debit', 'credit'])
                cur.execute(sql, [start, end] + params)
                for r in cur.fetchall():
                    d, acct, desc, deb, cred = r
                    w.writerow([d, acct, desc, f"{float(deb or 0):.2f}", f"{float(cred or 0):.2f}"])


def try_fallback_filters(conn, f, year: int):
    """If initial filter yields zero rows, drop account filter and report available accounts."""
    date_col = f['date_col']
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT COUNT(*) FROM banking_transactions WHERE EXTRACT(YEAR FROM {date_col})=%s AND {f['where']}",
            [year] + f['params']
        )
        row = cur.fetchone()
        cnt = int(row[0]) if row and len(row) > 0 and row[0] is not None else 0
        if cnt:
            return f
        # Print sample accounts for this year to guide selection
        account_col = f.get('account_col')
        if account_col:
            try:
                cur.execute(
                    f"""
                    SELECT {account_col}, COUNT(*)
                    FROM banking_transactions
                    WHERE EXTRACT(YEAR FROM {date_col})=%s
                    GROUP BY 1
                    ORDER BY 2 DESC
                    LIMIT 10
                    """,
                    [year],
                )
                samples = cur.fetchall() or []
                if samples:
                    print('ℹ️ No rows for the provided account filter. Top accounts for the year:')
                    for acc, c in samples:
                        print(f"   - {acc}: {c} txns")
            except Exception:
                pass
        # Fallback: no filter
        f2 = f.copy()
        f2['where'] = 'TRUE'
        f2['params'] = []
        print('[WARN] Falling back to all accounts (no account filter).')
        return f2


def main():
    ap = argparse.ArgumentParser(description='Generate monthly banking reconciliation report')
    ap.add_argument('--account', type=str, required=False, help='Bank account identifier (e.g., 1000)')
    ap.add_argument('--year', type=int, required=True)
    ap.add_argument('--details', action='store_true', help='Write per-month detail CSVs')
    ap.add_argument('--outdir', type=str, default='exports/banking')
    args = ap.parse_args()

    base_outdir = os.path.join(args.outdir, args.account or 'all', str(args.year))
    ensure_dir(base_outdir)

    try:
        with psycopg2.connect(**DSN) as conn:
            cols = get_columns(conn, 'banking_transactions')
            if not cols:
                raise SystemExit('banking_transactions table not found')
            f = build_filters(cols, args.account)
            # Smart fallback if no rows for given account
            f = try_fallback_filters(conn, f, args.year)

            # Summary
            summary_csv = os.path.join(base_outdir, 'banking_monthly_summary.csv')
            cats_csv = os.path.join(base_outdir, 'banking_monthly_categories.csv')

            print('🧮 Generating monthly summary...')
            s_rows = monthly_summary(conn, f, args.year, summary_csv)
            print(f'   ✓ Wrote {s_rows} monthly summary rows -> {summary_csv}')

            print('🗂️  Generating monthly category breakdown...')
            c_rows = monthly_categories(conn, f, args.year, cats_csv)
            print(f'   ✓ Wrote {c_rows} category rows -> {cats_csv}')

            if args.details:
                print('📄 Writing per-month details...')
                monthly_details(conn, f, args.year, base_outdir)

            print('[OK] Banking reconciliation report complete.')
            print('   Folder:', base_outdir)
    except Exception as e:
        print('[FAIL] Error:', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
