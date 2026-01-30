#!/usr/bin/env python3
"""
Read-only probe: find Interac e-transfer in CIBC data by amount/name/date.
- Searches banking_transactions (PostgreSQL) for credits within a date window
  and with description containing Interac/e-transfer and optional name tokens.
- Falls back to scanning local CIBC CSV files for the same.

Usage examples:
  python scripts/search_interac_in_cibc.py --date 2025-10-07 --amount 300 --name "HAYLEY LUSH"
"""
import argparse
import csv
import os
import sys
from datetime import datetime, timedelta

try:
    import psycopg2  # type: ignore
except Exception:
    psycopg2 = None

DB_CONFIG = {
    'dbname': os.environ.get('DB_NAME', 'almsdata'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', '***REDACTED***'),
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', '5432'))
}

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CIBC_ROOT = os.path.join(WORKSPACE_ROOT, 'CIBC UPLOADS')


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--date', required=True, help='Target date YYYY-MM-DD')
    p.add_argument('--amount', type=float, required=True, help='Credit amount, e.g. 300.00')
    p.add_argument('--name', default='', help='Optional payer name tokens, e.g. "HAYLEY LUSH"')
    p.add_argument('--days', type=int, default=3, help='Window +/- days around date (default 3)')
    return p.parse_args()


def search_db(target_date: str, amount: float, name_tokens: list, days: int):
    if psycopg2 is None:
        return []
    start = (datetime.fromisoformat(target_date) - timedelta(days=days)).date()
    end = (datetime.fromisoformat(target_date) + timedelta(days=days)).date()
    clauses = [
        "(description ILIKE '%E-TRANSFER%' OR description ILIKE '%INTERAC%')",
        "credit_amount = %s",
        "transaction_date BETWEEN %s AND %s",
    ]
    params = [amount, start, end]
    for tok in name_tokens:
        clauses.append("description ILIKE %s")
        params.append(f"%{tok}%")
    sql = f"""
        SELECT transaction_id, transaction_date, description, credit_amount, account_number
        FROM banking_transactions
        WHERE {' AND '.join(clauses)}
        ORDER BY transaction_date DESC
    """
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        return rows
    except Exception as e:
        print(f"[DB] query failed: {e}")
        return []


def search_csvs(target_date: str, amount: float, name_tokens: list, days: int):
    start = (datetime.fromisoformat(target_date) - timedelta(days=days))
    end = (datetime.fromisoformat(target_date) + timedelta(days=days))
    hits = []
    for root, _, files in os.walk(CIBC_ROOT):
        for fn in files:
            if not fn.lower().endswith('.csv'):
                continue
            path = os.path.join(root, fn)
            try:
                with open(path, newline='', encoding='utf-8-sig') as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if not row:
                            continue
                        # Expect date, description, debit, credit or similar
                        try:
                            d = datetime.fromisoformat(row[0])
                        except Exception:
                            # try alt mm/dd/yyyy
                            try:
                                d = datetime.strptime(row[0], '%m/%d/%Y')
                            except Exception:
                                continue
                        if not (start.date() <= d.date() <= end.date()):
                            continue
                        desc = (row[1] if len(row) > 1 else '').upper()
                        credit = None
                        if len(row) > 3 and row[3]:
                            try:
                                credit = float(str(row[3]).replace(',', ''))
                            except Exception:
                                credit = None
                        elif len(row) > 2 and row[2]:
                            # Some files place credit in column 2
                            try:
                                credit = float(str(row[2]).replace(',', ''))
                            except Exception:
                                credit = None
                        if credit is None or abs(credit - amount) > 0.009:
                            continue
                        if 'E-TRANSFER' not in desc and 'INTERAC' not in desc:
                            continue
                        if any(tok not in desc for tok in name_tokens):
                            continue
                        hits.append((path, d.date().isoformat(), desc, credit))
            except Exception:
                continue
    return hits


def main():
    args = parse_args()
    tokens = [t.strip().upper() for t in args.name.split() if t.strip()]

    print(f"Searching DB banking_transactions for {args.date} ±{args.days}d amount={args.amount} name={' '.join(tokens) or '(none)'}")
    db_rows = search_db(args.date, args.amount, tokens, args.days)
    if db_rows:
        for r in db_rows:
            print(f"DB HIT: id={r[0]} date={r[1]} amt={r[3]} acct={r[4]} desc={r[2]}")
    else:
        print("No DB hits (or DB not reachable).")

    print(f"\nSearching local CIBC CSVs under '{CIBC_ROOT}' ...")
    csv_hits = search_csvs(args.date, args.amount, tokens, args.days)
    if csv_hits:
        for h in csv_hits:
            print(f"CSV HIT: file={h[0]} date={h[1]} amt={h[3]} desc={h[2]}")
    else:
        print("No CSV hits in date window.")

    if not db_rows and not csv_hits:
        print("\nLikely reasons: (1) Deposit not yet accepted (email shows 'Claim your deposit'), (2) October CIBC CSVs not downloaded/imported yet, (3) Different destination account.")

if __name__ == '__main__':
    main()
