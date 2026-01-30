#!/usr/bin/env python3
"""
Ingest missing 2012 banking transactions (idempotent, dry-run by default).

Usage examples:
  python -X utf8 scripts/ingest_missing_banking_transactions_2012.py \
    --input L:\\limo\\staging\\2012_comparison\\missing_cibc_transactions_normalized.csv \
    --account CIBC-2012

Flags:
  --write      Apply inserts (default: dry-run)
  --input      CSV path with columns: transaction_date, description, debit_amount, credit_amount, source_reference
  --account    Value to place into banking_transactions.account_number if the column exists (optional)

Idempotence:
- Skips any row already present (same date, same amounts, same normalized description)
- No deletions performed

Defensive schema use:
- Detects available columns in banking_transactions and only writes to those
"""
from __future__ import annotations
import argparse
from pathlib import Path
import csv
import os
from decimal import Decimal, InvalidOperation
import psycopg2
from datetime import datetime, date

DEFAULT_INPUT = Path(r"L:\\limo\\staging\\2012_comparison\\missing_cibc_transactions_normalized.csv")


def get_conn():
    host = os.environ.get('DB_HOST', 'localhost')
    dbname = os.environ.get('DB_NAME', 'almsdata')
    user = os.environ.get('DB_USER', 'postgres')
    password = os.environ.get('DB_PASSWORD', '***REDACTED***')
    return psycopg2.connect(host=host, dbname=dbname, user=user, password=password)


def get_columns(cur, table: str) -> set[str]:
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
    """, (table,))
    return {r[0] for r in cur.fetchall()}


def to_decimal(s: str | None) -> Decimal:
    if not s:
        return Decimal('0')
    try:
        return Decimal(str(s).replace(',', '').strip())
    except InvalidOperation:
        return Decimal('0')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', default=str(DEFAULT_INPUT))
    ap.add_argument('--account', default=None)
    ap.add_argument('--infer-account', action='store_true', help='Infer a valid account_number from existing banking_transactions when not provided')
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--from-date', dest='from_date', help='Inclusive start date (YYYY-MM-DD) for filtering input rows')
    ap.add_argument('--to-date', dest='to_date', help='Inclusive end date (YYYY-MM-DD) for filtering input rows')
    args = ap.parse_args()

    path = Path(args.input)
    if not path.exists():
        print(f"Input not found: {path}")
        return

    conn = get_conn()
    conn.autocommit = False
    cur = conn.cursor()
    cols = get_columns(cur, 'banking_transactions')

    can_account = 'account_number' in cols
    has_desc = 'description' in cols
    if not has_desc:
        print("ERROR: banking_transactions.description column not found; aborting for safety.")
        cur.close(); conn.close(); return

    # Prepare statements
    sel_sql = (
        "SELECT transaction_id FROM banking_transactions "
        "WHERE transaction_date = %s "
        "AND COALESCE(credit_amount,0) = %s "
        "AND COALESCE(debit_amount,0) = %s "
        "AND LOWER(TRIM(description)) = LOWER(TRIM(%s)) "
        "LIMIT 1"
    )

    insert_cols = ['transaction_date','description','debit_amount','credit_amount']
    inferred_account = None
    if can_account:
        if args.account:
            inferred_account = args.account
        elif args.infer_account:
            # Try to infer: pick most common account_number among recent data
            try:
                cur.execute("SELECT account_number, COUNT(*) c FROM banking_transactions GROUP BY account_number ORDER BY c DESC LIMIT 1")
                row = cur.fetchone()
                if row and row[0]:
                    inferred_account = row[0]
            except Exception:
                pass
            if inferred_account is None:
                try:
                    cur.execute("SELECT account_number FROM banking_transactions LIMIT 1")
                    row = cur.fetchone()
                    if row and row[0]:
                        inferred_account = row[0]
                except Exception:
                    pass
        if inferred_account:
            insert_cols.append('account_number')
    insert_sql = "INSERT INTO banking_transactions ({cols}) VALUES ({vals})".format(
        cols=", ".join(insert_cols),
        vals=", ".join(["%s"] * len(insert_cols))
    )

    total = 0
    existing = 0
    planned = 0
    inserted = 0

    # Parse date filters
    fd = td = None
    if args.from_date:
        fd = datetime.strptime(args.from_date, '%Y-%m-%d').date()
    if args.to_date:
        td = datetime.strptime(args.to_date, '%Y-%m-%d').date()

    with open(path, 'r', encoding='utf-8', newline='') as f:
        r = csv.DictReader(f)
        for row in r:
            total += 1
            d = row.get('transaction_date')
            desc = (row.get('description') or '').strip()
            debit = to_decimal(row.get('debit_amount'))
            credit = to_decimal(row.get('credit_amount'))
            if not d or not desc:
                continue
            # Apply date filter if provided
            try:
                dt = datetime.strptime(d, '%Y-%m-%d').date()
            except Exception:
                continue
            if fd and dt < fd:
                continue
            if td and dt > td:
                continue
            cur.execute(sel_sql, (d, credit, debit, desc))
            if cur.fetchone():
                existing += 1
                continue
            values = [d, desc, debit, credit]
            if can_account and inferred_account:
                values.append(inferred_account)
            planned += 1
            if args.write:
                cur.execute(insert_sql, values)
                inserted += 1

    if args.write:
        conn.commit()
    else:
        conn.rollback()

    cur.close(); conn.close()

    mode = 'APPLIED' if args.write else 'DRY-RUN'
    print(f"{mode}: processed {total}, existing {existing}, planned {planned}, inserted {inserted}")


if __name__ == '__main__':
    main()
