#!/usr/bin/env python3
"""
Import lender statement transactions into Postgres for reconciliation.

Usage:
  python scripts/import_lender_statement.py "docs/Statement1_from_Heffner_....mht" --run-extractor --dry-run
  python scripts/import_lender_statement.py "docs/lender_statement_parsed.csv"

Behavior:
  - If input is .mht and --run-extractor, call the extractor to produce rows.
  - Create table lender_statement_transactions if not exists.
  - Upsert rows keyed by (txn_date, amount, desc_hash) to avoid duplicates.
"""

import argparse
import csv
import hashlib
import os
import subprocess
from datetime import datetime

import psycopg2

DB_CONFIG = {
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***',
    'host': 'localhost',
    'port': 5432
}

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS lender_statement_transactions (
    id SERIAL PRIMARY KEY,
    txn_date DATE NOT NULL,
    description TEXT NOT NULL,
    amount NUMERIC(12,2) NOT NULL,
    balance NUMERIC(12,2),
    source_file TEXT,
    desc_hash VARCHAR(32) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (txn_date, amount, desc_hash)
);
"""

def md5_32(s: str) -> str:
    return hashlib.md5(s.encode('utf-8')).hexdigest()

def run_extractor(mht_path: str) -> list[dict]:
    """Run the MHT extractor and capture CSV rows in-memory."""
    cmd = [
        os.path.join('L:/limo/.venv/Scripts', 'python.exe'),
        'scripts/extract_lender_statement_mht.py',
        mht_path
    ]
    out = subprocess.check_output(cmd, text=True, encoding='utf-8', errors='ignore')
    lines = [l for l in out.splitlines() if l.strip()]
    # Skip header if present
    if lines and lines[0].lower().startswith('date,'):
        lines = lines[1:]
    rows = []
    for line in lines:
        parts = line.split(',')
        if len(parts) < 4:
            continue
        date_str = parts[0].strip()
        desc = ','.join(parts[1:-2]).strip()
        amount = parts[-2].strip()
        balance = parts[-1].strip()
        try:
            txn_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            amt = round(float(amount), 2)
            bal = round(float(balance), 2) if balance else None
        except Exception:
            continue
        rows.append({'date': txn_date, 'description': desc, 'amount': amt, 'balance': bal})
    return rows

def load_csv(csv_path: str) -> list[dict]:
    rows = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                txn_date = datetime.strptime(r['date'], '%Y-%m-%d').date()
                amt = round(float(r['amount']), 2)
                bal = round(float(r.get('balance') or '0'), 2)
                rows.append({'date': txn_date, 'description': r['description'], 'amount': amt, 'balance': bal})
            except Exception:
                continue
    return rows

def upsert_rows(conn, rows: list[dict], source_file: str, dry_run: bool):
    cur = conn.cursor()
    cur.execute(CREATE_TABLE_SQL)
    inserted = 0
    for r in rows:
        desc_hash = md5_32(r['description'])
        if dry_run:
            inserted += 1
            continue
        cur.execute(
            """
            INSERT INTO lender_statement_transactions (txn_date, description, amount, balance, source_file, desc_hash)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (txn_date, amount, desc_hash) DO UPDATE
                SET balance = EXCLUDED.balance,
                    source_file = EXCLUDED.source_file
            """,
            (r['date'], r['description'], r['amount'], r['balance'], source_file, desc_hash)
        )
        inserted += 1
    if not dry_run:
        conn.commit()
    return inserted

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input', help='Parsed CSV or original .mht file')
    ap.add_argument('--run-extractor', action='store_true', help='Run MHT extractor if input is .mht')
    ap.add_argument('--dry-run', action='store_true', help='Do not write to DB, only report counts')
    args = ap.parse_args()

    source_file = args.input
    if not os.path.exists(source_file):
        print(f"File not found: {source_file}")
        return

    if source_file.lower().endswith('.mht') and args.run_extractor:
        rows = run_extractor(source_file)
    elif source_file.lower().endswith('.csv'):
        rows = load_csv(source_file)
    else:
        print('Unsupported input. Provide .csv, or .mht with --run-extractor')
        return

    print(f"Rows parsed: {len(rows)}")
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        inserted = upsert_rows(conn, rows, source_file, args.dry_run)
        print(f"Rows {'validated' if args.dry_run else 'upserted'}: {inserted}")
    finally:
        conn.close()

if __name__ == '__main__':
    main()
