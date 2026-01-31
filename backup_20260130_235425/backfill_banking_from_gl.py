"""
Backfill banking_transactions for missing years (2013-2016) by parsing QuickBooks General_ledger.xlsx directly.
- Parses the Excel with header rows, forward-fills Account to tag each row
- Targets bank account(s) by name heuristics (e.g., 'CIBC checking account')
- Maps rows to banking schema; balance left null
- Limits to 2013-2016 to avoid duplicating existing 2012 and 2017+
- Idempotent: checks for existing rows by (date, description, debit, credit, account_number)
"""
import os
import re
import sys
from datetime import datetime
import psycopg2
import pandas as pd

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


def parse_general_ledger_excel(file_path: str) -> pd.DataFrame:
    """Parse the General_ledger.xlsx with header rows, forward-fill Account, coerce types."""
    df = pd.read_excel(file_path, header=4)
    # Normalize columns
    df.columns = df.columns.str.strip()
    # Build account_name from either 'Account' or header column (often in first column)
    first_col = df.columns[0]
    df['__account_src'] = None
    if 'Account' in df.columns:
        df['__account_src'] = df['Account']
    if first_col and first_col not in ['Date', 'Transaction Type', '#', 'Name', 'Memo/Description', 'Debit', 'Credit', 'Balance']:
        # Often contains the account header like '0228362 CIBC checking account'
        df['__account_src'] = df['__account_src'].fillna(df[first_col])
    # Forward fill to propagate header value into transaction rows
    df['__account_src'] = df['__account_src'].ffill()
    # Map to normalized names
    col_map = {
        'Date': 'transaction_date',
        'Memo/Description': 'description',
        'Debit': 'debit_amount',
        'Credit': 'credit_amount',
    '__account_src': 'account_name',
        'Name': 'entity_name',
    }
    for old, new in col_map.items():
        if old in df.columns:
            df[new] = df[old]
    # Keep only rows with dates
    df = df[df['transaction_date'].notna()].copy()
    # Types
    df['transaction_date'] = pd.to_datetime(df['transaction_date'], errors='coerce', dayfirst=True)
    df = df[df['transaction_date'].notna()].copy()
    df['debit_amount'] = pd.to_numeric(df['debit_amount'], errors='coerce').fillna(0.0)
    df['credit_amount'] = pd.to_numeric(df['credit_amount'], errors='coerce').fillna(0.0)
    for c in ['description', 'account_name', 'entity_name']:
        if c in df.columns:
            df[c] = df[c].fillna('').astype(str)
        else:
            df[c] = ''
    return df


def extract_account_number(account_code: str) -> str:
    if not account_code:
        return None
    m = re.match(r"^(\d{4,})", account_code.strip())
    if m:
        return m.group(1)
    # fallback: digits anywhere
    digits = re.findall(r"\d+", account_code)
    return digits[0] if digits else None


def filter_accounts(df: pd.DataFrame) -> list:
    accounts = sorted(set([a for a in df['account_name'].dropna().astype(str).unique() if a.strip()]))
    bank_like = []
    for a in accounts:
        low = a.lower()
        if any(k in low for k in ['checking', 'chequing', 'bank', 'cibc', 'rbc', 'td', 'scotia']):
            bank_like.append(a)
    return bank_like


def summarize(df):
    df['year'] = pd.to_datetime(df['transaction_date']).dt.year
    counts = df.groupby('year').size().to_dict()
    return counts


def existing_key_set(cur, years):
    """Fetch existing (date, desc, debit, credit, account_number) keys for the target years to dedupe."""
    year_min = min(years)
    year_max = max(years)
    cur.execute("""
        SELECT transaction_date, COALESCE(description,''), COALESCE(debit_amount,0), COALESCE(credit_amount,0), COALESCE(account_number,'')
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) BETWEEN %s AND %s
    """, (year_min, year_max))
    return set(cur.fetchall())


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Backfill banking from General_ledger.xlsx')
    parser.add_argument('--years', default='2013,2014,2015,2016', help='Comma-separated years to import')
    parser.add_argument('--file', default='L:\\limo\\quickbooks\\Arrow Limousine backup 2025 Oct 19, 2025\\General_ledger.xlsx', help='Path to General_ledger.xlsx')
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing')
    args = parser.parse_args()

    years = tuple(int(y.strip()) for y in args.years.split(',') if y.strip())

    # Parse Excel and filter accounts
    df_all = parse_general_ledger_excel(args.file)
    if df_all.empty:
        print('[FAIL] Could not parse any rows from General_ledger.xlsx')
        sys.exit(1)
    accounts = filter_accounts(df_all)
    if not accounts:
        print('[FAIL] No bank-like accounts detected in Excel')
        sys.exit(1)
    preferred = [a for a in accounts if 'cibc' in a.lower() and 'checking' in a.lower()] or accounts
    print('Candidate bank accounts (Excel):')
    for a in preferred[:10]:
        print(f'  - {a}')
    df = df_all[df_all['account_name'].isin(preferred)].copy()
    df['year'] = df['transaction_date'].dt.year
    df = df[df['year'].isin(years)].copy()
    counts = summarize(df)
    print('\nGL transactions by year (selected accounts):')
    for y in sorted(counts):
        print(f'  {y}: {counts[y]}')

    # DB connection for write/dedupe
    conn = get_conn()
    try:
        cur = conn.cursor()
        # Build inserts
        inserts = []
        for _, r in df.iterrows():
            acc_num = extract_account_number(r['account_name'])
            inserts.append((
                acc_num,
                r['transaction_date'],
                (r['description'] or '').strip(),
                float(r['debit_amount'] or 0.0),
                float(r['credit_amount'] or 0.0),
                (r['entity_name'] or None),
                None,  # category
            ))

        print(f"\nPrepared {len(inserts)} candidate banking rows for {years}")

        # Dedupe against existing
        existing = existing_key_set(cur, years)
        to_write = [row for row in inserts if (row[1], row[2] or '', row[3] or 0.0, row[4] or 0.0, row[0] or '') not in existing]
        print(f"Deduplicated: {len(inserts) - len(to_write)} existing, {len(to_write)} to insert")

        if args.dry_run:
            print('\n[OK] DRY RUN: no changes written')
            return

        # Insert
        inserted = 0
        for row in to_write:
            cur.execute(
                """
                INSERT INTO banking_transactions (account_number, transaction_date, description, debit_amount, credit_amount, vendor_name, category)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                row,
            )
            if cur.rowcount > 0:
                inserted += 1
        conn.commit()
        print(f"\n[OK] Inserted {inserted} banking rows for years {years}")
    finally:
        try:
            conn.close()
        except:
            pass


if __name__ == '__main__':
    main()
