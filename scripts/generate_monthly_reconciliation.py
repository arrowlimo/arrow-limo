#!/usr/bin/env python3
"""
Generate Monthly Reconciliation Reports (Schema-Aware)
=====================================================

Produces per-month reconciliation summaries for a given year and account identifier.
- Attempts to match the provided identifier to banking account_number directly
  or via bank_accounts.gl_account_code when available.
- For each month: opening balance, total deposits (credits), withdrawals (debits), closing balance.
- Category breakdown per month (uses `category` if available; else inferred from description/vendor columns).

Outputs:
  exports/reconciliation/<account_label>/<year>/index.csv       (monthly summary)
  exports/reconciliation/<account_label>/<year>/<YYYY-MM>.csv   (detail by category)

Usage:
  python -X utf8 scripts/generate_monthly_reconciliation.py --year 2012 --account 1000

Safe: Read-only; adapts to available schemas.
"""
from __future__ import annotations

import os
import sys
import csv
import argparse
import calendar
from datetime import date, datetime
import psycopg2
from psycopg2.extras import DictCursor

DSN = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)


def cols(conn, table: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s
            """,
            (table,),
        )
        return {r[0] for r in cur.fetchall()}


def pick_first(available: set[str], *candidates: str) -> str | None:
    for c in candidates:
        if c in available:
            return c
    return None


def resolve_accounts(conn, account_identifier: str) -> tuple[list[str], str]:
    """Return list of banking account_numbers to include and a label for output path.
    If direct match exists in banking_transactions.account_number, use it.
    Else, try bank_accounts.gl_account_code == account_identifier.
    Fallback: all accounts (with label 'all_accounts').
    """
    bt_cols = cols(conn, "banking_transactions")
    account_col = pick_first(bt_cols, "account_number", "account")
    if account_col:
        with conn.cursor() as cur:
            cur.execute(f"SELECT DISTINCT {account_col} FROM banking_transactions")
            all_accounts = [r[0] for r in cur.fetchall() if r and r[0]]
        # direct match
        if account_identifier in all_accounts:
            return [account_identifier], account_identifier

    # try bank_accounts map
    ba_cols = cols(conn, "bank_accounts")
    if ba_cols:
        gl_code_col = pick_first(ba_cols, "gl_account_code", "account_code", "gl_code")
        acct_num_col = pick_first(ba_cols, "account_number", "number")
        if gl_code_col and acct_num_col:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {acct_num_col} FROM bank_accounts WHERE {gl_code_col}::text = %s",
                    (str(account_identifier),),
                )
                rows = [r[0] for r in cur.fetchall() if r and r[0]]
                if rows:
                    label = str(account_identifier)
                    return rows, label

    # fallback: all
    return [], "all_accounts"


def month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def fetch_month_data(conn, accounts: list[str], label: str, year: int, month: int) -> dict:
    bt_cols = cols(conn, "banking_transactions")
    if not bt_cols:
        return {}
    date_col = pick_first(bt_cols, "transaction_date", "trans_date", "date")
    debit_col = pick_first(bt_cols, "debit_amount", "debit")
    credit_col = pick_first(bt_cols, "credit_amount", "credit")
    balance_col = pick_first(bt_cols, "balance", "running_balance")
    category_col = pick_first(bt_cols, "category")
    desc_col = pick_first(bt_cols, "description", "vendor_name", "memo")
    account_col = pick_first(bt_cols, "account_number", "account")

    if not (date_col and debit_col and credit_col):
        return {}

    start, end = month_bounds(year, month)

    where = [f"{date_col} BETWEEN %s AND %s"]
    params: list = [start, end]
    if accounts and account_col:
        where.append(f"{account_col} = ANY(%s)")
        params.append(accounts)

    base_where = " AND ".join(where)

    summary = {
        "year": year,
        "month": month,
        "start": start,
        "end": end,
        "deposits": 0.0,
        "withdrawals": 0.0,
        "opening": None,
        "closing": None,
        "categories": [],
    }

    with conn.cursor() as cur:
        # deposits/withdrawals
        cur.execute(
            f"""
            SELECT COALESCE(SUM({credit_col}),0) AS deposits,
                   COALESCE(SUM({debit_col}),0)  AS withdrawals
            FROM banking_transactions
            WHERE {base_where}
            """,
            params,
        )
        row = cur.fetchone() or (0, 0)
        summary["deposits"] = float(row[0] or 0.0)
        summary["withdrawals"] = float(row[1] or 0.0)

        # opening/closing balances (if available)
        if balance_col:
            cur.execute(
                f"""
                SELECT {balance_col}
                FROM banking_transactions
                WHERE {base_where}
                ORDER BY {date_col} ASC, {balance_col} ASC
                LIMIT 1
                """,
                params,
            )
            op = cur.fetchone()
            summary["opening"] = float(op[0]) if op and op[0] is not None else None

            cur.execute(
                f"""
                SELECT {balance_col}
                FROM banking_transactions
                WHERE {base_where}
                ORDER BY {date_col} DESC, {balance_col} DESC
                LIMIT 1
                """,
                params,
            )
            cl = cur.fetchone()
            summary["closing"] = float(cl[0]) if cl and cl[0] is not None else None

        # categories
        cat_expr = category_col if category_col else (desc_col if desc_col else None)
        if cat_expr:
            cur.execute(
                f"""
                SELECT COALESCE({cat_expr}, '') AS cat,
                       COALESCE(SUM({credit_col}),0) AS deposits,
                       COALESCE(SUM({debit_col}),0)  AS withdrawals
                FROM banking_transactions
                WHERE {base_where}
                GROUP BY 1
                ORDER BY 2 DESC, 3 DESC
                """,
                params,
            )
            summary["categories"] = [(r[0], float(r[1] or 0.0), float(r[2] or 0.0)) for r in cur.fetchall()]

    return summary


def write_month_files(outdir: str, label: str, year: int, month: int, data: dict):
    ensure_dir(outdir)
    # detail per month
    month_str = f"{year}-{month:02d}"
    detail_path = os.path.join(outdir, f"{month_str}.csv")
    with open(detail_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category", "deposits", "withdrawals"])
        for cat, dep, wd in data.get("categories", []):
            w.writerow([cat, f"{dep:.2f}", f"{wd:.2f}"])
    return detail_path


def write_index(outdir: str, rows: list[dict]):
    ensure_dir(outdir)
    index_path = os.path.join(outdir, "index.csv")
    with open(index_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["period_end", "opening", "deposits", "withdrawals", "closing"])
        for r in rows:
            period_end = r["end"].isoformat()
            w.writerow([
                period_end,
                f"{(r['opening'] if r['opening'] is not None else 0.0):.2f}",
                f"{r['deposits']:.2f}",
                f"{r['withdrawals']:.2f}",
                f"{(r['closing'] if r['closing'] is not None else 0.0):.2f}",
            ])
    return index_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--account", type=str, required=True, help="Account identifier (account_number or GL code, e.g. 1000)")
    args = ap.parse_args()

    year = args.year
    account_id = args.account

    try:
        with psycopg2.connect(**DSN) as conn:
            accounts, label = resolve_accounts(conn, account_id)
            outdir = os.path.join("exports", "reconciliation", label, str(year))

            monthly_rows: list[dict] = []
            for m in range(1, 13):
                data = fetch_month_data(conn, accounts, label, year, m)
                if not data:
                    continue
                # write per-month detail
                write_month_files(outdir, label, year, m, data)
                monthly_rows.append(data)

            if not monthly_rows:
                print("[WARN] No banking data found for the specified filters.")
                print(f"   Account label: {label}; year: {year}")
                sys.exit(0)

            index_path = write_index(outdir, monthly_rows)
            print("[OK] Monthly reconciliation generated:")
            print("  Index:", index_path)
            print("  Detail files: one per month in", outdir)
    except Exception as e:
        print("[FAIL] Error:", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
