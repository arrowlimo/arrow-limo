#!/usr/bin/env python
"""
Import semi-structured bank statement text into banking_transactions.

Input format: tab-delimited columns with headers similar to
Date \t Transactions \t Debit \t Credit \t Running Balance

Features:
- Robust parsing of dates like "Jan. 04, 2012"
- Amount parsing with $ and commas; supports negatives
- Derives debit_amount vs credit_amount
- Idempotent inserts via duplicate check; optional source_hash if column exists
- Dry-run by default; use --write to commit

Assumptions:
- Account number provided via --account (e.g., 00339)
- Connects to Postgres using get_db_connection() from api.py (DB_* env vars)
"""
import argparse
import csv
import os
import re
from datetime import datetime
from typing import Optional, Tuple

import psycopg2

# Ensure project root is on sys.path to import api.py
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from api import get_db_connection  # Reuse project helper


DATE_PAT = re.compile(r"^(\w{3})\.?\s+(\d{1,2}),\s*(\d{4})$")
MONTHS = {m.lower(): i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def parse_date(s: str) -> datetime.date:
    s = s.strip()
    m = DATE_PAT.match(s)
    if not m:
        raise ValueError(f"Unrecognized date: {s}")
    mon, day, year = m.groups()
    mon = mon[:3].lower()
    month_num = MONTHS.get(mon)
    if not month_num:
        raise ValueError(f"Unrecognized month in date: {s}")
    return datetime(int(year), month_num, int(day)).date()


def parse_amount(s: str) -> Optional[float]:
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    # Remove $ and commas and spaces
    s2 = s.replace("$", "").replace(",", "").strip()
    try:
        return float(s2)
    except ValueError:
        # Handle parentheses for negatives if present
        if s2.startswith("(") and s2.endswith(")"):
            s3 = s2[1:-1]
            return -float(s3)
        raise


def get_table_columns(cur, table: str) -> set:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        """,
        (table,),
    )
    return {r[0] for r in cur.fetchall()}


def normalize_description(desc: str) -> str:
    return re.sub(r"\s+", " ", desc).strip()


def source_fingerprint(date, desc, debit, credit, balance) -> str:
    key = f"{date.isoformat()}|{normalize_description(desc)}|{debit or 0:.2f}|{credit or 0:.2f}|{balance if balance is not None else 0:.2f}"
    # Deterministic shorter fingerprint
    import hashlib

    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def parse_lines(lines: list[str]) -> list[dict]:
    rows = []
    header_seen = False
    for raw in lines:
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        parts = line.split("\t")
        # Some rows may be shorter/longer; pad to 5 columns
        while len(parts) < 5:
            parts.append("")
        date_s, desc, debit_s, credit_s, balance_s = parts[:5]
        if not header_seen and date_s.strip().lower().startswith("date"):
            header_seen = True
            continue
        # Skip footer lines if any
        try:
            date = parse_date(date_s)
        except Exception:
            # If date not recognized but header already handled, skip
            continue
        debit = parse_amount(debit_s)
        credit = parse_amount(credit_s)
        balance = parse_amount(balance_s)
        desc = normalize_description(desc)
        rows.append(
            {
                "transaction_date": date,
                "description": desc,
                "debit_amount": round(debit, 2) if debit is not None else 0.0,
                "credit_amount": round(credit, 2) if credit is not None else 0.0,
                "balance": round(balance, 2) if balance is not None else None,
            }
        )
    return rows


def insert_rows(conn, account: str, rows: list[dict], dry_run: bool = True) -> Tuple[int, int]:
    cur = conn.cursor()
    cols = get_table_columns(cur, "banking_transactions")
    has_source_hash = "source_hash" in cols
    inserted = 0
    skipped = 0
    for r in rows:
        fp = source_fingerprint(r["transaction_date"], r["description"], r["debit_amount"], r["credit_amount"], r["balance"])
        params = {
            "account_number": account,
            "transaction_date": r["transaction_date"],
            "description": r["description"],
            "debit_amount": r["debit_amount"],
            "credit_amount": r["credit_amount"],
            "balance": r["balance"],
        }
        if has_source_hash:
            params["source_hash"] = fp
        # Build dynamic insert
        insert_cols = [k for k in params.keys() if k in cols]
        placeholders = ", ".join([f"%({k})s" for k in insert_cols])
        collist = ", ".join(insert_cols)
        # Duplicate check
        cur.execute(
            """
            SELECT 1 FROM banking_transactions
            WHERE transaction_date=%s AND description=%s AND debit_amount=%s AND credit_amount=%s
            LIMIT 1
            """,
            (
                r["transaction_date"],
                r["description"],
                r["debit_amount"],
                r["credit_amount"],
            ),
        )
        if cur.fetchone():
            skipped += 1
            continue
        if dry_run:
            inserted += 1
        else:
            cur.execute(f"INSERT INTO banking_transactions ({collist}) VALUES ({placeholders})", params)
            inserted += 1
    if not dry_run:
        conn.commit()
    cur.close()
    return inserted, skipped


def main():
    ap = argparse.ArgumentParser(description="Import bank statement text into banking_transactions")
    ap.add_argument("--file", required=True, help="Path to .txt with tab-delimited bank data")
    ap.add_argument("--account", required=True, help="Bank account number (e.g., 00339)")
    ap.add_argument("--write", action="store_true", help="Apply changes (default dry-run)")
    args = ap.parse_args()

    if not os.path.exists(args.file):
        print(f"ERROR: File not found: {args.file}")
        return 2

    with open(args.file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    rows = parse_lines(lines)
    print(f"Parsed rows: {len(rows)}")
    if not rows:
        return 1

    # Preview a few
    for r in rows[:5]:
        print(f"  {r['transaction_date']} | {r['description'][:80]} | D {r['debit_amount']:.2f} | C {r['credit_amount']:.2f} | Bal {r['balance']}")

    conn = get_db_connection()
    try:
        inserted, skipped = insert_rows(conn, args.account, rows, dry_run=not args.write)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    mode = "APPLY" if args.write else "DRY-RUN"
    print(f"\n{mode}: would insert {inserted} rows, skip {skipped} duplicates")
    if args.write:
        print("Committed to banking_transactions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
