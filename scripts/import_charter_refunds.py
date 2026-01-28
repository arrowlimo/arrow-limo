#!/usr/bin/env python3
"""
Import charter/customer refunds from Excel/CSV reports and link them to charters.

- Scans a directory recursively for *.xlsx, *.xls, *.csv
- Detects refund rows via keywords and/or negative amounts
- Attempts linkage to charters via:
  1) reserve_number parsed from description/memo
  2) matching payments.square_payment_id / square_transaction_id
- Writes rows into charter_refunds table (idempotent)
- Creates/refreshes a summary view charter_refund_summary

Usage:
  python scripts/import_charter_refunds.py --paths "L:\\limo\\Square reports" --write
"""
import os
import re
import sys
import argparse
from decimal import Decimal, InvalidOperation
from datetime import datetime

import psycopg2
from psycopg2.extras import execute_values

try:
    import pandas as pd  # type: ignore
except Exception:
    pd = None

from dotenv import load_dotenv
load_dotenv('l:/limo/.env'); load_dotenv()

DB_HOST = os.getenv('DB_HOST','localhost')
DB_PORT = int(os.getenv('DB_PORT','5432'))
DB_NAME = os.getenv('DB_NAME','almsdata')
DB_USER = os.getenv('DB_USER','postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD','')

RESERVE_RE = re.compile(r"\b(\d{6})\b")
MONEY_STRIP = ['$',',']

CANDIDATE_COLS = {
    'date': ['date','transaction date','created','created at','refund date','posted date'],
    'amount': ['amount','refund amount','total','net amount'],
    'description': ['description','memo','details','note','notes'],
    'square_id': ['payment id','card payment id','transaction id','payment reference','source transaction id','square payment id','reference id','reference'],
    'customer': ['customer','buyer','client','name']
}

def get_conn():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)

def normalize_amount(v):
    if v is None: return Decimal('0')
    s = str(v).strip()
    if not s: return Decimal('0')
    for ch in MONEY_STRIP: s = s.replace(ch,'')
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]
    try:
        return Decimal(s)
    except InvalidOperation:
        try:
            return Decimal(str(float(s)))
        except Exception:
            return Decimal('0')

def parse_date(v):
    if pd is not None and isinstance(v, (pd.Timestamp,)):
        return v.date()
    s = str(v).strip()
    for fmt in ['%Y-%m-%d','%m/%d/%Y','%d-%m-%Y','%b %d, %Y','%d %b %Y','%y-%m-%d','%m-%d-%y']:
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    return None

def looks_like_refund(text):
    if not text: return False
    t = str(text).lower()
    return ('refund' in t) or ('refunded' in t) or ('reversal' in t) or ('chargeback' in t)

def detect_columns(df):
    cols = {c.lower().strip(): c for c in df.columns}
    mapping = {}
    for key, alts in CANDIDATE_COLS.items():
        for a in alts:
            if a in cols:
                mapping[key] = cols[a]
                break
    return mapping

def scan_files(paths):
    files = []
    for root in paths:
        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                if fn.lower().endswith(('.xlsx','.xls','.csv')) and 'refund' in fn.lower():
                    files.append(os.path.join(dirpath, fn))
    return files

def ensure_schema(cur):
    cur.execute('''
        CREATE TABLE IF NOT EXISTS charter_refunds (
            id SERIAL PRIMARY KEY,
            refund_date DATE NOT NULL,
            amount NUMERIC(12,2) NOT NULL,
            reserve_number VARCHAR(20),
            charter_id INTEGER,
            payment_id INTEGER,
            square_payment_id VARCHAR(100),
            description TEXT,
            customer TEXT,
            source_file TEXT,
            source_row INTEGER,
            reference TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
    # Helpful indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_charter_refunds_reserve ON charter_refunds(reserve_number)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_charter_refunds_date ON charter_refunds(refund_date)")
    # Summary view
    cur.execute('''
        CREATE OR REPLACE VIEW charter_refund_summary AS
        SELECT c.reserve_number,
               c.charter_id,
               COALESCE(SUM(cr.amount),0) AS total_refunded,
               COUNT(*) AS refund_count
        FROM charters c
        LEFT JOIN charter_refunds cr ON cr.reserve_number = c.reserve_number
        GROUP BY c.reserve_number, c.charter_id
    ''')


def link_to_charter(cur, reserve_number, square_payment_id):
    charter_id = None
    if reserve_number:
        cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (reserve_number,))
        r = cur.fetchone()
        if r:
            charter_id = r[0]
    payment_id = None
    if square_payment_id:
        # try payments link
        cur.execute("SELECT payment_id, reserve_number FROM payments WHERE square_payment_id = %s LIMIT 1", (square_payment_id,))
        r = cur.fetchone()
        if r:
            payment_id = r[0]
            if not reserve_number and r[1]:
                reserve_number = r[1]
                if not charter_id:
                    cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (reserve_number,))
                    r2 = cur.fetchone()
                    if r2:
                        charter_id = r2[0]
    return reserve_number, charter_id, payment_id


def import_refunds(paths, write=False):
    if pd is None:
        print("[FAIL] pandas not available. Please install pandas and openpyxl.")
        return 0, []
    conn = get_conn(); cur = conn.cursor()
    ensure_schema(cur)

    files = scan_files(paths)
    print(f"Found {len(files)} refund files in: {paths}")

    inserted = 0
    inserted_rows = []

    for fp in files:
        print(f"\nParsing refunds from: {fp}")
        try:
            if fp.lower().endswith('.csv'):
                df = pd.read_csv(fp, dtype=str, encoding='utf-8-sig')
            else:
                df = pd.read_excel(fp, dtype=str)
        except Exception as e:
            print(f"  ⚠ Failed to open {fp}: {e}")
            continue
        # Normalize
        df = df.fillna('')
        mapping = detect_columns(df)
        if not mapping:
            print("  ⚠ No recognizable columns. Skipping.")
            continue
        # Iterate rows
        for idx, row in df.iterrows():
            desc = row.get(mapping.get('description',''), '') if mapping.get('description') else ''
            amt_raw = row.get(mapping.get('amount',''), '') if mapping.get('amount') else ''
            date_raw = row.get(mapping.get('date',''), '') if mapping.get('date') else ''
            sqid = row.get(mapping.get('square_id',''), '') if mapping.get('square_id') else ''
            customer = row.get(mapping.get('customer',''), '') if mapping.get('customer') else ''

            # Filter: must look like a refund OR amount negative (or column flagged)
            amount = normalize_amount(amt_raw)
            if not looks_like_refund(desc) and amount >= 0:
                # Not a refund row, skip
                continue

            refund_date = parse_date(date_raw)
            if not refund_date:
                # try to parse any date-like from desc
                refund_date = None
            # Extract reserve number from description if possible
            reserve = None
            m = RESERVE_RE.search(desc)
            if m:
                reserve = m.group(1)

            # Link to charter via reserve or square_payment_id
            reserve, charter_id, payment_id = link_to_charter(cur, reserve, sqid)

            # Check duplicate
            cur.execute("""
                SELECT 1 FROM charter_refunds
                WHERE refund_date = %s AND amount = %s AND COALESCE(reserve_number,'') = COALESCE(%s,'')
                  AND COALESCE(square_payment_id,'') = COALESCE(%s,'') AND source_file = %s AND source_row = %s
            """, (refund_date, amount, reserve, sqid, fp, int(idx)))
            if cur.fetchone():
                continue

            cur.execute("""
                INSERT INTO charter_refunds
                (refund_date, amount, reserve_number, charter_id, payment_id, square_payment_id, description, customer, source_file, source_row, reference)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (refund_date, amount, reserve, charter_id, payment_id, sqid, desc, customer, fp, int(idx), sqid))
            inserted += 1
            inserted_rows.append((refund_date, amount, reserve, charter_id, payment_id, sqid, fp, int(idx)))

    if write:
        conn.commit()
    else:
        conn.rollback()
    cur.close(); conn.close()
    return inserted, inserted_rows


def main():
    ap = argparse.ArgumentParser(description='Import charter refunds from Excel/CSV files')
    ap.add_argument('--paths', nargs='+', default=[r'L:\\limo\\Square reports'], help='Directories to scan')
    ap.add_argument('--write', action='store_true', help='Commit inserts (otherwise dry run)')
    args = ap.parse_args()

    print('='*100)
    print('IMPORT CHARTER REFUNDS FROM SPREADSHEETS')
    print('='*100)
    print(f"Paths: {args.paths}")

    count, rows = import_refunds(args.paths, write=args.write)
    if args.write:
        print(f"\n✓ Inserted {count} refund rows into charter_refunds")
    else:
        print(f"\nDRY RUN: Would insert {count} refund rows. Use --write to apply.")

    # Print quick summary from DB
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM charter_refunds")
    total_count, total_amount = cur.fetchone()
    print(f"\nCurrent charter_refunds table: {total_count} rows, total amount ${total_amount:,.2f}")
    # Top 10 by amount
    cur.execute("""
        SELECT reserve_number, COUNT(*), SUM(amount)
        FROM charter_refunds
        GROUP BY reserve_number
        ORDER BY SUM(amount) DESC NULLS LAST
        LIMIT 10
    """)
    print("\nTop reserve_numbers by refunded total:")
    for rn, cnt, amt in cur.fetchall():
        print(f"  {rn}: {cnt} refunds, ${amt:,.2f}")
    cur.close(); conn.close()

if __name__ == '__main__':
    main()
