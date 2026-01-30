#!/usr/bin/env python3
"""
Monthly Bank Reconciliation Generator (Schema-aware, Read-only)
===============================================================

Generates, for a given account and year:
- One monthly summary CSV (per month): totals of debits, credits, net; counts; fees/NSF subtotals
- One monthly detail CSV (per month): line-by-line with normalized columns
- One year overview CSV: month rollups

Output folder:
  exports/reconciliation/<year>/account_<account>/
    - overview_<year>.csv
    - <year>-<mm>_summary.csv
    - <year>-<mm>_detail.csv

Args:
  --account 1000            (required) account_number string match
  --year 2012               (required) year integer
  --include-vendor          include vendor_name if available
  --include-category        include category if available

Notes:
- Tries to detect date, debit, credit, description, vendor, category columns.
- Month boundaries are calendar months; statement end = last calendar day.
- Safe read-only. No DB writes.
"""
from __future__ import annotations

import os
import sys
import csv
import argparse
from datetime import date, datetime, timedelta
import calendar
import psycopg2
from psycopg2.extras import DictCursor

DSN = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)


def get_columns(cur, table: str) -> set[str]:
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        """,
        (table,),
    )
    return {r[0] for r in cur.fetchall()}


def detect_schema(cols: set[str]) -> dict:
    date_col = None
    for c in ("transaction_date", "trans_date", "date", "posted_date"):
        if c in cols:
            date_col = c
            break
    debit_col = None
    for c in ("debit_amount", "debit", "withdrawal"):
        if c in cols:
            debit_col = c
            break
    credit_col = None
    for c in ("credit_amount", "credit", "deposit"):
        if c in cols:
            credit_col = c
            break
    desc_col = None
    for c in ("description", "memo", "details", "narrative"):
        if c in cols:
            desc_col = c
            break
    vendor_col = "vendor_name" if "vendor_name" in cols else None
    category_col = "category" if "category" in cols else None
    acct_col = "account_number" if "account_number" in cols else None
    balance_col = "balance" if "balance" in cols else None
    return dict(
        date=date_col, debit=debit_col, credit=credit_col, desc=desc_col,
        vendor=vendor_col, category=category_col, account=acct_col, balance=balance_col,
    )


def month_range(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end = date(year, month, last_day)
    return start, end


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def fetch_month(cur, schema: dict, account: str, start: date, end: date) -> list[dict]:
    where_parts = []
    params = []

    # account filter
    if schema["account"]:
        where_parts.append(f"{schema['account']} = %s")
        params.append(account)
    # date filter
    if schema["date"]:
        where_parts.append(f"{schema['date']} BETWEEN %s AND %s")
        params.extend([start, end])

    where_sql = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""

    select_cols = []
    select_cols.append(f"{schema['date']} AS tx_date" if schema["date"] else "NULL::date AS tx_date")
    select_cols.append(f"{schema['desc']} AS description" if schema["desc"] else "''::text AS description")
    select_cols.append(f"{schema['debit']} AS debit" if schema["debit"] else "0::numeric AS debit")
    select_cols.append(f"{schema['credit']} AS credit" if schema["credit"] else "0::numeric AS credit")
    select_cols.append(f"{schema['vendor']} AS vendor_name" if schema["vendor"] else "''::text AS vendor_name")
    select_cols.append(f"{schema['category']} AS category" if schema["category"] else "''::text AS category")
    select_cols.append(f"{schema['balance']} AS balance" if schema["balance"] else "NULL::numeric AS balance")

    sql = f"""
        SELECT {', '.join(select_cols)}
        FROM banking_transactions
        {where_sql}
        ORDER BY tx_date ASC
    """
    cur.execute(sql, params)
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def summarize_month(rows: list[dict]) -> dict:
    total_debit = 0.0
    total_credit = 0.0
    fees = 0.0
    nsf = 0.0
    for r in rows:
        d = float(r.get("debit") or 0.0)
        c = float(r.get("credit") or 0.0)
        total_debit += d
        total_credit += c
        desc = (r.get("description") or "").lower()
        if "nsf" in desc or "non-sufficient" in desc:
            nsf += d or 0.0
        if "fee" in desc or "charge" in desc or "service" in desc:
            # very rough: count any debit with these words as fee
            fees += d or 0.0
    net = total_credit - total_debit
    return dict(total_debit=total_debit, total_credit=total_credit, net=net, fees=fees, nsf=nsf, count=len(rows))


def breakdown(rows: list[dict], key: str) -> list[tuple[str, int, float, float]]:
    agg = {}
    for r in rows:
        k = (r.get(key) or "").strip()
        d = float(r.get("debit") or 0.0)
        c = float(r.get("credit") or 0.0)
        if k not in agg:
            agg[k] = [0, 0.0, 0.0]
        agg[k][0] += 1
        agg[k][1] += d
        agg[k][2] += c
    # sort by net outflow abs
    out = []
    for k, (cnt, deb, cred) in agg.items():
        out.append((k, cnt, deb, cred))
    out.sort(key=lambda x: (x[2]-x[3]), reverse=True)
    return out


def write_month_files(out_dir: str, y: int, m: int, rows: list[dict], sums: dict):
    mm = f"{m:02d}"
    # Detail
    detail_path = os.path.join(out_dir, f"{y}-{mm}_detail.csv")
    with open(detail_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["tx_date", "description", "vendor_name", "category", "debit", "credit", "balance"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({
                "tx_date": r.get("tx_date"),
                "description": r.get("description"),
                "vendor_name": r.get("vendor_name"),
                "category": r.get("category"),
                "debit": f"{float(r.get('debit') or 0.0):.2f}",
                "credit": f"{float(r.get('credit') or 0.0):.2f}",
                "balance": f"{float(r.get('balance') or 0.0):.2f}" if r.get("balance") is not None else "",
            })
    # Summary (top categories/vendors)
    summary_path = os.path.join(out_dir, f"{y}-{mm}_summary.csv")
    cat = breakdown(rows, "category")
    ven = breakdown(rows, "vendor_name")
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["STATEMENT PERIOD", f"{y}-{mm}-01 to {y}-{mm}-{calendar.monthrange(y, m)[1]}"])
        w.writerow(["TOTAL DEBITS", f"{sums['total_debit']:.2f}", "TOTAL CREDITS", f"{sums['total_credit']:.2f}", "NET", f"{sums['net']:.2f}"])
        w.writerow(["FEES", f"{sums['fees']:.2f}", "NSF", f"{sums['nsf']:.2f}", "COUNT", sums['count']])
        w.writerow([])
        w.writerow(["BY CATEGORY", "count", "debits", "credits"])
        for k, cnt, deb, cred in cat:
            w.writerow([k, cnt, f"{deb:.2f}", f"{cred:.2f}"])
        w.writerow([])
        w.writerow(["BY VENDOR", "count", "debits", "credits"])
        for k, cnt, deb, cred in ven:
            w.writerow([k, cnt, f"{deb:.2f}", f"{cred:.2f}"])
    return detail_path, summary_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", required=True, help="Account number to filter (e.g., 1000 for CIBC)")
    ap.add_argument("--year", type=int, required=True)
    args = ap.parse_args()

    year = args.year
    account = args.account

    out_base = os.path.join("exports", "reconciliation", str(year), f"account_{account}")
    ensure_dir(out_base)

    try:
        with psycopg2.connect(**DSN) as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cols = get_columns(cur, "banking_transactions")
                if not cols:
                    print("[FAIL] No banking_transactions table found")
                    sys.exit(1)
                schema = detect_schema(cols)
                if not schema["date"] or not schema["account"]:
                    print("[FAIL] Required columns missing (date/account)")
                    sys.exit(1)

                # overview
                overview_rows = []
                for m in range(1, 13):
                    start, end = month_range(year, m)
                    rows = fetch_month(cur, schema, account, start, end)
                    sums = summarize_month(rows)
                    detail_path, summary_path = write_month_files(out_base, year, m, rows, sums)
                    overview_rows.append({
                        "month": f"{year}-{m:02d}",
                        "count": sums["count"],
                        "total_debit": f"{sums['total_debit']:.2f}",
                        "total_credit": f"{sums['total_credit']:.2f}",
                        "net": f"{sums['net']:.2f}",
                        "fees": f"{sums['fees']:.2f}",
                        "nsf": f"{sums['nsf']:.2f}",
                        "detail_csv": os.path.basename(detail_path),
                        "summary_csv": os.path.basename(summary_path),
                    })

                # write overview
                overview_path = os.path.join(out_base, f"overview_{year}.csv")
                with open(overview_path, "w", newline="", encoding="utf-8") as f:
                    fieldnames = ["month", "count", "total_debit", "total_credit", "net", "fees", "nsf", "detail_csv", "summary_csv"]
                    w = csv.DictWriter(f, fieldnames=fieldnames)
                    w.writeheader()
                    for r in overview_rows:
                        w.writerow(r)
                print("[OK] Monthly reconciliation generated at:")
                print("  ", overview_path)
                return 0
    except Exception as e:
        print("[FAIL] Error:", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
