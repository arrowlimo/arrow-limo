#!/usr/bin/env python3
"""
Import Staged Banking CSVs (Idempotent)
======================================

Reads normalized CSVs from exports/banking/imported_csv and inserts them into
banking_transactions with defensive schema handling and hashing to prevent duplicates.

Usage:
  python -X utf8 scripts/import_staged_banking_csvs.py --year 2012 --dir exports/banking/imported_csv --account 0228362 --dry-run
  python -X utf8 scripts/import_staged_banking_csvs.py --year 2012 --apply

Behavior:
- Supports multiple column variants: date, amount, debit_amount/credit_amount, description/memo/vendor
- Determines debit vs credit when only a single Amount column is present
- Computes source_hash = sha256(date|description|debit|credit|account_number)
- Inserts only when hash not already present (idempotent)
- Never deletes or updates existing rows

Safety:
- Dry-run by default; use --apply to write
"""
from __future__ import annotations

import os
import sys
import csv
import glob
import argparse
import hashlib
from datetime import datetime
from decimal import Decimal, InvalidOperation

import psycopg2

DSN = dict(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
    port=int(os.environ.get('DB_PORT', '5432')),
)


def parse_amount(val: str) -> Decimal:
    if val is None:
        return Decimal('0')
    s = str(val).strip().replace(',', '')
    if s in ('', 'NA', 'N/A', 'null', 'None'):
        return Decimal('0')
    try:
        return Decimal(s)
    except InvalidOperation:
        # Remove currency symbols
        s = s.replace('$', '')
        try:
            return Decimal(s)
        except InvalidOperation:
            return Decimal('0')


def normalize_row(header_map: dict[str, int], row: list[str], acct: str, year: int) -> dict | None:
    def get(*names):
        for n in names:
            if n in header_map:
                return row[header_map[n]].strip()
        return ''

    # Date
    date_str = get('transaction_date', 'date', 'Date')
    if not date_str:
        return None
    # Try multiple formats
    dt = None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%Y/%m/%d'):
        try:
            dt = datetime.strptime(date_str, fmt).date()
            break
        except Exception:
            continue
    if dt is None:
        # Try Excel-like serial dates not implemented; skip
        return None
    if dt.year != year:
        return None

    desc = get('description', 'memo', 'vendor', 'Merchant', 'Description')

    # Amount handling
    debit = credit = Decimal('0')
    if 'debit_amount' in header_map or 'credit_amount' in header_map:
        debit = parse_amount(get('debit_amount', 'Debit', 'debit'))
        credit = parse_amount(get('credit_amount', 'Credit', 'credit'))
    else:
        amt = parse_amount(get('amount', 'Amount'))
        # Convention: negative = money out (debit), positive = money in (credit)
        if amt < 0:
            debit = -amt
            credit = Decimal('0')
        else:
            credit = amt
            debit = Decimal('0')

    # Build source_hash
    raw_key = f"{dt.isoformat()}|{desc}|{debit}|{credit}|{acct}"
    source_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

    return dict(
        account_number=acct,
        transaction_date=dt,
        description=desc,
        debit_amount=str(debit),
        credit_amount=str(credit),
        source_hash=source_hash,
    )


def get_existing_hashes(conn) -> set[str]:
    try:
        with conn.cursor() as cur:
            # Ensure table exists
            cur.execute("""
                SELECT 1 FROM information_schema.tables
                WHERE table_schema='public' AND table_name='banking_transactions'
            """)
            if cur.fetchone() is None:
                print("[FAIL] banking_transactions table not found. Create tables before import.")
                return set()
            # Ensure column exists
            cur.execute("""
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='banking_transactions' AND column_name='source_hash'
            """)
            has_hash = cur.fetchone() is not None
            if not has_hash:
                print("[WARN] banking_transactions.source_hash not found. Import will work but idempotency is reduced.")
                return set()
            cur.execute("SELECT source_hash FROM banking_transactions WHERE source_hash IS NOT NULL")
            return {r[0] for r in cur.fetchall()}
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print("[WARN] Could not prefetch existing hashes:", e)
        return set()


def upsert_rows(conn, rows: list[dict], apply: bool, import_batch: str, source_file: str) -> tuple[int, int]:
    inserted = 0
    skipped = 0
    if not rows:
        return inserted, skipped
    # Detect schema columns
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name='banking_transactions'
            """
        )
        cols = {r[0] for r in cur.fetchall()}

    def maybe_col(name: str) -> bool:
        return name in cols

    has_hash = maybe_col('source_hash')
    has_desc = maybe_col('description')
    has_date = maybe_col('transaction_date')
    has_debit = maybe_col('debit_amount')
    has_credit = maybe_col('credit_amount')
    has_account = maybe_col('account_number')

    for r in rows:
        # Build INSERT dynamically based on available columns
        fields = ['account_number', 'transaction_date', 'description', 'debit_amount', 'credit_amount']
        values = [r['account_number'], r['transaction_date'], r['description'], Decimal(r['debit_amount']), Decimal(r['credit_amount'])]
        if has_hash:
            fields.append('source_hash'); values.append(r['source_hash'])
        if maybe_col('source_file'):
            fields.append('source_file'); values.append(source_file)
        if maybe_col('import_batch_id'):
            fields.append('import_batch_id'); values.append(import_batch)
        if maybe_col('import_batch') and 'import_batch_id' not in fields:
            fields.append('import_batch'); values.append(import_batch)
        # Idempotent insert guard
        placeholders = ','.join(['%s'] * len(values))
        if has_hash:
            sql = f"INSERT INTO banking_transactions ({', '.join(fields)})\n                   SELECT {placeholders}\n                   WHERE NOT EXISTS (SELECT 1 FROM banking_transactions WHERE source_hash = %s)"
            params = values + [r['source_hash']]
        else:
            # Fallback existence check using available columns
            where_clauses = []
            where_vals = []
            if has_account:
                where_clauses.append('account_number = %s'); where_vals.append(r['account_number'])
            if has_date:
                where_clauses.append('transaction_date = %s'); where_vals.append(r['transaction_date'])
            if has_desc:
                where_clauses.append('description = %s'); where_vals.append(r['description'])
            if has_debit:
                where_clauses.append('debit_amount = %s'); where_vals.append(Decimal(r['debit_amount']))
            if has_credit:
                where_clauses.append('credit_amount = %s'); where_vals.append(Decimal(r['credit_amount']))
            if where_clauses:
                where_sql = ' AND '.join(where_clauses)
                sql = f"INSERT INTO banking_transactions ({', '.join(fields)})\n                       SELECT {placeholders}\n                       WHERE NOT EXISTS (SELECT 1 FROM banking_transactions WHERE {where_sql})"
                params = values + where_vals
            else:
                # No guard possible; perform plain insert
                sql = f"INSERT INTO banking_transactions ({', '.join(fields)}) VALUES ({placeholders})"
                params = values
        if apply:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                if cur.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1
        else:
            # Dry-run: simulate skip if exists
            skipped += 0
    return inserted, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='exports/banking/imported_csv')
    ap.add_argument('--year', type=int, required=True)
    ap.add_argument('--account', default='0228362')
    ap.add_argument('--apply', action='store_true', help='Write changes (default dry-run)')
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.dir, '*.csv')))
    if not files:
        print(f"[FAIL] No CSV files found under {args.dir}")
        sys.exit(1)

    import_batch = f"bankcsv-{args.year}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    total_rows = 0
    total_inserted = 0
    total_skipped = 0

    try:
        with psycopg2.connect(**DSN) as conn:
            conn.autocommit = True  # Avoid transaction abort cascades on read errors
            try:
                existing = get_existing_hashes(conn)
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                existing = set()
            for path in files:
                count = 0
                prepared: list[dict] = []
                with open(path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    headers = next(reader)
                    # Normalize header names to lowercase underscored
                    headers_norm = [h.strip().lower().replace(' ', '_') for h in headers]
                    header_map = {name: idx for idx, name in enumerate(headers_norm)}
                    for row in reader:
                        if args.limit and len(prepared) >= args.limit:
                            break
                        normalized = normalize_row(header_map, row, args.account, args.year)
                        if not normalized:
                            continue
                        # Skip if already exists in DB snapshot to avoid INSERT
                        if normalized['source_hash'] in existing:
                            total_skipped += 1
                            continue
                        prepared.append(normalized)
                        count += 1
                total_rows += count
                inserted, skipped = upsert_rows(conn, prepared, args.apply, import_batch, os.path.basename(path))
                total_inserted += inserted
                total_skipped += skipped
                print(f"📄 {os.path.basename(path)}: prepared={len(prepared)} inserted={inserted} skipped={skipped}")
            # autocommit enabled; no explicit commit required
            print("\nSummary:")
            print(f"  Files: {len(files)}")
            print(f"  Rows prepared: {total_rows}")
            print(f"  Inserted: {total_inserted}")
            print(f"  Skipped (existing): {total_skipped}")
            print(f"  Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    except Exception as e:
        print('[FAIL] Error:', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
