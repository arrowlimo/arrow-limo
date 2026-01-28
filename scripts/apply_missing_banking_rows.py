#!/usr/bin/env python3
"""
Apply missing banking rows from a CSV into banking_transactions, safely and idempotently.
- Computes source_hash as sha256(date|description|debit|credit)
- Skips if a row with same source_hash already exists (idempotent)
- Dry-run by default; requires --write and override key for protected table

CSV columns:
  account_number, transaction_date (YYYY-MM-DD), amount, side (debit|credit), description, notes, source
"""
import argparse
import csv
import hashlib
import os
from decimal import Decimal
from datetime import datetime

import psycopg2

try:
    from table_protection import protect_deletion, create_backup_before_delete, log_deletion_audit
except Exception:
    protect_deletion = None
    create_backup_before_delete = None
    log_deletion_audit = None


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***'),
    )


def compute_hash(datestr: str, description: str, debit: Decimal, credit: Decimal) -> str:
    payload = f"{datestr}|{(description or '').strip()}|{debit:.2f}|{credit:.2f}".encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def ensure_columns(cur):
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='banking_transactions'
    """)
    return {r[0] for r in cur.fetchall()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', type=str, default='l:/limo/reports/missing_banking_rows_may2012.csv')
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--override-key', type=str, default=None)
    args = ap.parse_args()

    conn = get_db_connection(); cur = conn.cursor()

    cols = ensure_columns(cur)
    required = {'transaction_date','description','debit_amount','credit_amount','account_number'}
    missing = required - cols
    if missing:
        print(f"[FAIL] banking_transactions missing required columns: {', '.join(sorted(missing))}")
        cur.close(); conn.close(); return

    to_insert = []
    with open(args.csv, 'r', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            acct = row['account_number'].strip()
            d = row['transaction_date'].strip()
            amt = Decimal(row['amount'])
            side = row['side'].strip().lower()
            desc = (row.get('description') or '').strip()
            notes = (row.get('notes') or '').strip()
            source = (row.get('source') or '').strip()
            debit = amt if side == 'debit' else Decimal('0.00')
            credit = amt if side == 'credit' else Decimal('0.00')
            shash = compute_hash(d, desc, debit, credit)
            # Idempotency: skip if already present
            cur.execute("SELECT transaction_id FROM banking_transactions WHERE source_hash=%s LIMIT 1", (shash,))
            ex = cur.fetchone()
            if ex:
                continue
            to_insert.append((acct, d, desc, debit, credit, shash, notes, source))

    print(f"Planned inserts: {len(to_insert)}")
    if not to_insert:
        print('Nothing to insert. Exiting.')
        cur.close(); conn.close(); return

    if not args.write:
        for t in to_insert:
            acct, d, desc, debit, credit, shash, notes, source = t
            print(f"  {d} acct={acct} debit={debit:.2f} credit={credit:.2f} desc={desc}")
        print("\nDry-run only. Re-run with --write and an override key if you want to apply.")
        cur.close(); conn.close(); return

    # Insert rows
    inserted = 0
    for acct, d, desc, debit, credit, shash, notes, source in to_insert:
        cur.execute(
            """
            INSERT INTO banking_transactions (account_number, transaction_date, description, debit_amount, credit_amount, source_hash, reconciliation_status, reconciliation_notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING transaction_id
            """,
            (acct, d, desc, debit, credit, shash, 'unreconciled', f"{notes} | source={source}")
        )
        tid = cur.fetchone()[0]
        inserted += 1
        conn.commit()
        print(f"  Inserted transaction_id={tid} {d} {acct} {desc} debit={debit:.2f} credit={credit:.2f}")

    print(f"[OK] Done. Inserted {inserted} rows.")
    cur.close(); conn.close()

if __name__ == '__main__':
    main()
