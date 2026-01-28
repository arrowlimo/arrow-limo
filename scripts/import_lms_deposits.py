#!/usr/bin/env python3
"""
Import LMS Deposit.csv into Postgres table lms_deposits.

Source CSV path default: l:/limo/docs/Deposit.csv

Schema created:
  lms_deposits(id PK, cb_no TEXT, dep_date DATE, dep_key TEXT, number TEXT,
               total NUMERIC(12,2), transact TEXT, type TEXT, last_updated DATE,
               last_updated_by TEXT, row_hash VARCHAR(32), UNIQUE(dep_date, dep_key, number, total))

Idempotent: upsert on (dep_date, dep_key, number, total).
"""
import os
import csv
import argparse
from datetime import datetime
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv('l:/limo/.env'); load_dotenv()

DB_HOST = os.getenv('DB_HOST','localhost')
DB_PORT = int(os.getenv('DB_PORT','5432'))
DB_NAME = os.getenv('DB_NAME','almsdata')
DB_USER = os.getenv('DB_USER','postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD','')

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS lms_deposits (
    id SERIAL PRIMARY KEY,
    cb_no TEXT,
    dep_date DATE NOT NULL,
    dep_key TEXT,
    number TEXT,
    total NUMERIC(12,2) NOT NULL,
    transact TEXT,
    type TEXT,
    last_updated DATE,
    last_updated_by TEXT,
    row_hash VARCHAR(32),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (dep_date, dep_key, number, total)
);
"""


def get_conn():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def md5_32(s: str) -> str:
    return hashlib.md5(s.encode('utf-8')).hexdigest()


def parse_date(s: str):
    s = (s or '').strip()
    if not s:
        return None
    for fmt in ('%m/%d/%Y', '%m/%d/%y', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    return None


def parse_amount(s: str):
    s = (s or '').replace('$', '').replace(',', '').strip()
    if not s:
        return None
    try:
        return round(float(s), 2)
    except Exception:
        return None


def load_rows(path: str):
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            dep_date = parse_date(row.get('Date'))
            total = parse_amount(row.get('Total'))
            if not dep_date or total is None:
                continue
            cb_no = (row.get('CB_NO') or '').strip() or None
            dep_key = (row.get('Key') or '').strip() or None
            number = (row.get('Number') or '').strip() or None
            transact = (row.get('Transact') or '').strip() or None
            typ = (row.get('Type') or '').strip() or None
            last_updated = parse_date(row.get('LastUpdated') or '')
            last_by = (row.get('LastUpdatedBy') or '').strip() or None
            rh = md5_32('|'.join([
                str(cb_no or ''), dep_date.isoformat(), str(dep_key or ''), str(number or ''), f"{total:.2f}",
                str(transact or ''), str(typ or ''), str(last_updated or ''), str(last_by or '')
            ]))
            rows.append({
                'cb_no': cb_no, 'dep_date': dep_date, 'dep_key': dep_key, 'number': number,
                'total': total, 'transact': transact, 'type': typ,
                'last_updated': last_updated, 'last_updated_by': last_by, 'row_hash': rh
            })
    return rows


def upsert_rows(rows, dry_run: bool):
    inserted = 0
    updated = 0
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(CREATE_SQL)
            for r in rows:
                if dry_run:
                    inserted += 1
                    continue
                cur.execute(
                    """
                    INSERT INTO lms_deposits (cb_no, dep_date, dep_key, number, total, transact, type, last_updated, last_updated_by, row_hash)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (dep_date, dep_key, number, total) DO UPDATE
                       SET cb_no=EXCLUDED.cb_no,
                           transact=EXCLUDED.transact,
                           type=EXCLUDED.type,
                           last_updated=EXCLUDED.last_updated,
                           last_updated_by=EXCLUDED.last_updated_by,
                           row_hash=EXCLUDED.row_hash
                    """,
                    (r['cb_no'], r['dep_date'], r['dep_key'], r['number'], r['total'], r['transact'], r['type'], r['last_updated'], r['last_updated_by'], r['row_hash'])
                )
                inserted += 1
            if not dry_run:
                conn.commit()
    return inserted, updated


def main():
    ap = argparse.ArgumentParser(description='Import LMS Deposit.csv into lms_deposits table')
    ap.add_argument('--path', default=r'l:/limo/docs/Deposit.csv')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    if not os.path.exists(args.path):
        print(f"File not found: {args.path}")
        return
    rows = load_rows(args.path)
    print(f"Parsed rows: {len(rows)}")
    ins, upd = upsert_rows(rows, args.dry_run)
    print(f"Rows {'validated' if args.dry_run else 'upserted'}: {ins}")


if __name__ == '__main__':
    main()
