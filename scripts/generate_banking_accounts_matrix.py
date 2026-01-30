#!/usr/bin/env python3
"""
All-Accounts Banking Reconciliation Matrix
=========================================

Produces a comprehensive set of CSVs for a given year across ALL bank accounts:
- accounts_list.csv: distinct accounts with transaction counts for the year
- monthly_by_account.csv: per-account monthly totals (debits, credits, net, txns)
- monthly_categories_by_account.csv: per-account monthly category breakdown
- annual_totals_by_account.csv: per-account annual totals (debits, credits, net, txns)

Schema-aware: introspects column names in banking_transactions and adapts.
Debits = money out; Credits = money in.

Usage:
  python -X utf8 scripts/generate_banking_accounts_matrix.py --year 2012

Outputs under: exports/banking/all_accounts/<year>/

Env vars: DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT
"""
from __future__ import annotations

import os
import sys
import csv
import argparse
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


def build_schema(conn):
    cols = get_columns(conn, 'banking_transactions')
    if not cols:
        raise SystemExit('banking_transactions table not found')
    date_col = pick(cols, 'transaction_date', 'trans_date', 'date', 'posting_date') or 'transaction_date'
    debit = pick(cols, 'debit_amount', 'debit')
    credit = pick(cols, 'credit_amount', 'credit')
    account_col = pick(cols, 'account_number', 'account', 'account_code')
    category = pick(cols, 'category')
    if not (debit and credit and account_col and date_col):
        raise SystemExit('banking_transactions missing required columns (debit/credit/account/date)')
    desc_col = pick(cols, 'description', 'memo', 'vendor_name')
    return dict(date_col=date_col, debit=debit, credit=credit, account_col=account_col, category=category, desc_col=desc_col)


def write_accounts_list(conn, s, year: int, out_path: str) -> int:
    with conn.cursor() as cur, open(out_path, 'w', newline='', encoding='utf-8') as out:
        cur.execute(
            f"""
            SELECT {s['account_col']} AS account, COUNT(*) AS txns
            FROM banking_transactions
            WHERE EXTRACT(YEAR FROM {s['date_col']}) = %s
            GROUP BY 1
            ORDER BY txns DESC
            """,
            [year],
        )
        rows = cur.fetchall()
        w = csv.writer(out)
        w.writerow(['account', 'transactions'])
        for acc, tx in rows:
            w.writerow([acc, int(tx or 0)])
        return len(rows)


def write_monthly_by_account(conn, s, year: int, out_path: str) -> int:
    with conn.cursor() as cur, open(out_path, 'w', newline='', encoding='utf-8') as out:
        cur.execute(
            f"""
            SELECT
              date_trunc('month', {s['date_col']})::date AS month_start,
              (date_trunc('month', {s['date_col']}) + interval '1 month' - interval '1 day')::date AS month_end,
              {s['account_col']} AS account,
              COALESCE(SUM({s['debit']}),0) AS total_debits,
              COALESCE(SUM({s['credit']}),0) AS total_credits,
              COUNT(*) AS transactions
            FROM banking_transactions
            WHERE EXTRACT(YEAR FROM {s['date_col']}) = %s
            GROUP BY 1,2,3
            ORDER BY 3,1
            """,
            [year],
        )
        rows = cur.fetchall()
        w = csv.writer(out)
        w.writerow(['period_start', 'period_end', 'account', 'total_debits', 'total_credits', 'net_change', 'transactions'])
        for month_start, month_end, acc, deb, cred, tx in rows:
            net = float(cred or 0) - float(deb or 0)
            w.writerow([month_start, month_end, acc, f"{float(deb or 0):.2f}", f"{float(cred or 0):.2f}", f"{net:.2f}", int(tx or 0)])
        return len(rows)


def write_monthly_categories_by_account(conn, s, year: int, out_path: str) -> int:
    cat_expr = s['category'] if s['category'] else "''"
    with conn.cursor() as cur, open(out_path, 'w', newline='', encoding='utf-8') as out:
        cur.execute(
            f"""
            SELECT
              date_trunc('month', {s['date_col']})::date AS month_start,
              (date_trunc('month', {s['date_col']}) + interval '1 month' - interval '1 day')::date AS month_end,
              {s['account_col']} AS account,
              COALESCE({cat_expr}, 'uncategorized') AS category,
              COALESCE(SUM({s['debit']}),0) AS total_debits,
              COALESCE(SUM({s['credit']}),0) AS total_credits,
              COUNT(*) AS transactions
            FROM banking_transactions
            WHERE EXTRACT(YEAR FROM {s['date_col']}) = %s
            GROUP BY 1,2,3,4
            ORDER BY 3,1,5 DESC
            """,
            [year],
        )
        rows = cur.fetchall()
        w = csv.writer(out)
        w.writerow(['period_start', 'period_end', 'account', 'category', 'total_debits', 'total_credits', 'net_change', 'transactions'])
        for month_start, month_end, acc, cat, deb, cred, tx in rows:
            net = float(cred or 0) - float(deb or 0)
            w.writerow([month_start, month_end, acc, cat, f"{float(deb or 0):.2f}", f"{float(cred or 0):.2f}", f"{net:.2f}", int(tx or 0)])
        return len(rows)


def write_annual_totals_by_account(conn, s, year: int, out_path: str) -> int:
    with conn.cursor() as cur, open(out_path, 'w', newline='', encoding='utf-8') as out:
        cur.execute(
            f"""
            SELECT
              {s['account_col']} AS account,
              COALESCE(SUM({s['debit']}),0) AS total_debits,
              COALESCE(SUM({s['credit']}),0) AS total_credits,
              COUNT(*) AS transactions
            FROM banking_transactions
            WHERE EXTRACT(YEAR FROM {s['date_col']}) = %s
            GROUP BY 1
            ORDER BY 1
            """,
            [year],
        )
        rows = cur.fetchall()
        w = csv.writer(out)
        w.writerow(['account', 'total_debits', 'total_credits', 'net_change', 'transactions'])
        for acc, deb, cred, tx in rows:
            net = float(cred or 0) - float(deb or 0)
            w.writerow([acc, f"{float(deb or 0):.2f}", f"{float(cred or 0):.2f}", f"{net:.2f}", int(tx or 0)])
        return len(rows)


def main():
    ap = argparse.ArgumentParser(description='All-accounts banking reconciliation matrix')
    ap.add_argument('--year', type=int, required=True)
    ap.add_argument('--outdir', type=str, default='exports/banking/all_accounts')
    args = ap.parse_args()

    year_dir = os.path.join(args.outdir, str(args.year))
    ensure_dir(year_dir)

    try:
        with psycopg2.connect(**DSN) as conn:
            s = build_schema(conn)

            accounts_csv = os.path.join(year_dir, 'accounts_list.csv')
            monthly_csv = os.path.join(year_dir, 'monthly_by_account.csv')
            cats_csv = os.path.join(year_dir, 'monthly_categories_by_account.csv')
            annual_csv = os.path.join(year_dir, 'annual_totals_by_account.csv')

            print('📋 Listing accounts...')
            a_rows = write_accounts_list(conn, s, args.year, accounts_csv)
            print(f'   ✓ {a_rows} accounts -> {accounts_csv}')

            print('🧮 Monthly totals per account...')
            m_rows = write_monthly_by_account(conn, s, args.year, monthly_csv)
            print(f'   ✓ {m_rows} rows -> {monthly_csv}')

            print('🗂️  Monthly categories per account...')
            c_rows = write_monthly_categories_by_account(conn, s, args.year, cats_csv)
            print(f'   ✓ {c_rows} rows -> {cats_csv}')

            print('📊 Annual totals per account...')
            y_rows = write_annual_totals_by_account(conn, s, args.year, annual_csv)
            print(f'   ✓ {y_rows} rows -> {annual_csv}')

            print('[OK] All-accounts reconciliation matrix complete.')
            print('   Folder:', year_dir)
    except Exception as e:
        print('[FAIL] Error:', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
