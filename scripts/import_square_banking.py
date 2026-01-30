"""
Import Square transactions CSVs into banking_transactions for years 2014-2017.
- Handles multiple known file paths; you can pass --files with one or more files
- Defensive column mapping for Square exports: tries ['Date','Created Date','Payment Date'] and ['Amount','Net Total','Net']
- Sign handling: positive amounts treated as credit (money into bank), negative as debit
- Dedupe against existing by (date, description, debit, credit, account_number)
- Sets account_number to known CIBC account 0228362 by default (override via --account-number)
"""
import os
import sys
import csv
from datetime import datetime
import psycopg2
import pandas as pd
import hashlib

DEFAULT_ACCOUNT_NUMBER = '0228362'

DB_DEFAULTS = {
    'DB_HOST': 'localhost',
    'DB_NAME': 'almsdata',
    'DB_USER': 'postgres',
    'DB_PASSWORD': '***REDACTED***',
}

def env(name):
    return os.environ.get(name, DB_DEFAULTS[name])


def get_conn():
    return psycopg2.connect(
        host=env('DB_HOST'),
        dbname=env('DB_NAME'),
        user=env('DB_USER'),
        password=env('DB_PASSWORD'),
    )


def parse_square_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Normalize columns
    df.columns = [c.strip() for c in df.columns]
    # Candidate date columns
    date_cols = [c for c in df.columns if c.lower() in ['date','created date','payment date','deposit date','transaction date']]
    if not date_cols:
        raise ValueError(f'No date column found in {path} (columns: {list(df.columns)})')
    date_col = date_cols[0]
    # Candidate description
    desc_cols = [c for c in df.columns if c.lower() in ['description','activity','type','event']]
    desc_col = desc_cols[0] if desc_cols else None
    # Amount columns (prefer Net or Net Total)
    amount_cols_priority = ['Net Total','Net','Amount','Total']
    amount_col = None
    for c in amount_cols_priority:
        if c in df.columns:
            amount_col = c
            break
    if amount_col is None:
        # Try lower-case matching
        for c in df.columns:
            if c.lower() in ['net total','net','amount','total']:
                amount_col = c
                break
    if amount_col is None:
        raise ValueError(f'No amount column found in {path} (columns: {list(df.columns)})')
    # Build normalized frame
    out = pd.DataFrame()
    out['transaction_date'] = pd.to_datetime(df[date_col], errors='coerce')
    out = out[out['transaction_date'].notna()].copy()
    # Clean description
    if desc_col:
        out['description'] = df[desc_col].astype(str)
    else:
        out['description'] = 'Square transaction'
    # Parse amount and split to debit/credit
    amt = pd.to_numeric(df[amount_col], errors='coerce').fillna(0.0)
    out['credit_amount'] = amt.where(amt > 0, 0.0)
    out['debit_amount'] = (-amt).where(amt < 0, 0.0)
    out['vendor_name'] = 'Square'
    return out


def existing_key_set(cur, year_min: int, year_max: int, account_number: str):
    cur.execute(
        """
        SELECT transaction_date, COALESCE(description,''), COALESCE(debit_amount,0), COALESCE(credit_amount,0), COALESCE(account_number,'')
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) BETWEEN %s AND %s
          AND account_number = %s
        """,
        (year_min, year_max, account_number),
    )
    return set(cur.fetchall())


def get_banking_columns(cur):
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name='banking_transactions'
        ORDER BY ordinal_position
        """
    )
    return {r[0] for r in cur.fetchall()}


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Import Square CSVs into banking_transactions')
    parser.add_argument('--files', nargs='+', required=False, help='One or more Square CSV files')
    parser.add_argument('--account-number', default=DEFAULT_ACCOUNT_NUMBER, help='Bank account number for these deposits')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without writing')
    args = parser.parse_args()

    default_candidates = [
        r'L:\limo\qbb\backups\oldalms\COMPLETE-AUDIT-TRAIL\square payments\transactions-2014-01-01-2015-01-01.csv',
        r'L:\limo\qbb\New folder\Program Files\backups\oldalms\COMPLETE-AUDIT-TRAIL\square payments\transactions-2014-01-01-2015-01-01.csv',
        r'L:\limo\qbb\backups\oldalms\COMPLETE-AUDIT-TRAIL\square payments\transactions-2015-01-01-2016-01-01.csv',
        r'L:\limo\qbb\New folder\Program Files\backups\oldalms\COMPLETE-AUDIT-TRAIL\square payments\transactions-2015-01-01-2016-01-01.csv',
        r'L:\limo\qbb\backups\oldalms\COMPLETE-AUDIT-TRAIL\square payments\transactions-2016-01-01-2017-01-01.csv',
        r'L:\limo\qbb\New folder\Program Files\backups\oldalms\COMPLETE-AUDIT-TRAIL\square payments\transactions-2016-01-01-2017-01-01.csv',
    ]
    files = args.files or default_candidates
    files = [f for f in files if os.path.exists(f)]
    if not files:
        print('[FAIL] No Square CSV files found to import')
        sys.exit(1)

    frames = []
    failed = []
    for p in files:
        try:
            df = parse_square_csv(p)
            df['source_path'] = p
            frames.append(df)
            print(f"Parsed {len(df)} rows from {p}")
        except Exception as e:
            failed.append((p, str(e)))
            print(f"[WARN]  Failed to parse {p}: {e}")

    if not frames:
        print('[FAIL] No parseable Square CSV content')
        if failed:
            print('\nFailed files:')
            for p, e in failed:
                print(f'  - {p}: {e}')
        sys.exit(1)

    all_df = pd.concat(frames, ignore_index=True)
    # Focus on 2014-2017
    all_df['year'] = all_df['transaction_date'].dt.year
    all_df = all_df[all_df['year'].between(2014, 2017)]

    # Prepare rows (base fields)
    to_insert = []
    seen = set()
    for _, r in all_df.iterrows():
        acc = args.account_number
        date_val = r['transaction_date'].date()
        desc = str(r['description']).strip()
        debit = float(r['debit_amount'] or 0.0)
        credit = float(r['credit_amount'] or 0.0)
        key = (date_val, desc or '', debit or 0.0, credit or 0.0, acc or '')
        if key in seen:
            continue
        seen.add(key)
        # Build transaction hash for idempotency
        row_hash = hashlib.sha256(f"{date_val}|{acc}|{desc}|{debit}|{credit}".encode()).hexdigest()
        to_insert.append({
            'account_number': acc,
            'transaction_date': date_val,
            'description': desc,
            'debit_amount': debit,
            'credit_amount': credit,
            'category': 'square_payout',
            'vendor_extracted': 'Square',
            'source_file': r.get('source_path', None),
            'transaction_hash': row_hash,
        })

    # Dedupe
    conn = get_conn()
    try:
        cur = conn.cursor()
        existing = existing_key_set(cur, 2014, 2017, args.account_number)
        pre = len(to_insert)
        to_write = [row for row in to_insert if (row['transaction_date'], row['description'] or '', row['debit_amount'] or 0.0, row['credit_amount'] or 0.0, row['account_number'] or '') not in existing]
        print(f"\nSquare candidate rows: {pre}; existing: {pre - len(to_write)}; to insert: {len(to_write)}")

        if args.dry_run:
            print('\n[OK] DRY RUN: no changes written')
            if failed:
                print('\nFailed files:')
                for p, e in failed:
                    print(f'  - {p}: {e}')
            return

        # Determine available columns and build INSERT
        cols_available = get_banking_columns(cur)
        base_cols = ['account_number','transaction_date','description','debit_amount','credit_amount']
        optional_cols = []
        if 'category' in cols_available:
            optional_cols.append('category')
        if 'vendor_extracted' in cols_available:
            optional_cols.append('vendor_extracted')
        if 'source_file' in cols_available:
            optional_cols.append('source_file')
        if 'transaction_hash' in cols_available:
            optional_cols.append('transaction_hash')
        insert_cols = base_cols + optional_cols
        placeholders = ','.join(['%s'] * len(insert_cols))
        insert_sql = f"INSERT INTO banking_transactions ({','.join(insert_cols)}) VALUES ({placeholders})"

        inserted = 0
        for row in to_write:
            values = [row.get(c) for c in insert_cols]
            cur.execute(insert_sql, values)
            if cur.rowcount > 0:
                inserted += 1
        conn.commit()
        print(f"\n[OK] Inserted {inserted} Square banking rows")
        if failed:
            print('\nFailed files (skipped):')
            for p, e in failed:
                print(f'  - {p}: {e}')
    finally:
        try:
            conn.close()
        except:
            pass


if __name__ == '__main__':
    main()
