#!/usr/bin/env python3
"""
Top-up recent banking transactions from compiled CIBC CSVs without deleting existing rows.
- For each mapped account, find the current max(transaction_date) already in banking_transactions
- Insert only CSV rows with a strictly newer transaction_date
- Avoids FK violations and preserves prior reconciliations

Usage:
  python scripts/top_up_recent_banking_from_compiled_csv.py
"""
import os
from datetime import datetime

import pandas as pd
import psycopg2

DB_CONFIG = {
    'dbname': os.environ.get('DB_NAME', 'almsdata'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', '***REMOVED***'),
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', '5432')),
}

ACCOUNTS = {
    '8362': {
        'file': r'L:\limo\CIBC UPLOADS\0228362 (CIBC checking account)\cibc 8362 all.csv',
        'account_number': '0228362',
        'account_name': 'CIBC checking account',
    },
    '8117': {
        'file': r'L:\limo\CIBC UPLOADS\3648117 (CIBC Business Deposit account, alias for 0534\cibc 8117 all.csv',
        'account_number': '3648117',
        'account_name': 'CIBC Business Deposit account',
    },
    '4462': {
        'file': r'L:\limo\CIBC UPLOADS\8314462 (CIBC vehicle loans)\cibc 4462 all.csv',
        'account_number': '8314462',
        'account_name': 'CIBC vehicle loans',
    },
}

def get_max_date(cur, account_number):
    cur.execute("SELECT COALESCE(MAX(transaction_date), '1900-01-01'::date) FROM banking_transactions WHERE account_number=%s", (account_number,))
    return cur.fetchone()[0]


def import_new_rows(cur, file_path, account_number, account_name, min_date):
    if not os.path.exists(file_path):
        print(f"[FAIL] File not found: {file_path}")
        return 0

    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"[FAIL] Error reading {file_path}: {e}")
        return 0

    # Expect columns: Bank_id,Trans_date,Trans_description,Debit,Credit,Reconsiled_receipt_id,Reconsiled_receipt_total
    rename = {
        'Trans_date': 'transaction_date',
        'Trans_description': 'description',
        'Debit': 'debit_amount',
        'Credit': 'credit_amount',
    }
    for src, dst in rename.items():
        if src not in df.columns:
            print(f"[FAIL] Missing column {src} in {file_path}")
            return 0
    df = df.rename(columns=rename)

    df = df.dropna(subset=['transaction_date', 'description'])
    df['transaction_date'] = pd.to_datetime(df['transaction_date'], errors='coerce')
    df = df.dropna(subset=['transaction_date'])

    # Only strictly newer rows
    df_new = df[df['transaction_date'].dt.date > min_date].copy()
    if df_new.empty:
        print(f"  No newer rows for account {account_number} (max_date={min_date})")
        return 0

    # Normalize amounts
    for col in ['debit_amount', 'credit_amount']:
        df_new[col] = pd.to_numeric(df_new[col], errors='coerce').fillna(0)

    inserted = 0
    for _, row in df_new.iterrows():
        try:
            cur.execute(
                """
                INSERT INTO banking_transactions (
                    transaction_date, description, debit_amount, credit_amount,
                    balance, account_number, source_file
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    row['transaction_date'].date(),
                    row['description'],
                    row['debit_amount'] if row['debit_amount'] > 0 else None,
                    row['credit_amount'] if row['credit_amount'] > 0 else None,
                    0,
                    account_number,
                    os.path.basename(file_path),
                ),
            )
            inserted += 1
            # Commit in small batches to avoid large transactions
            if inserted % 1000 == 0:
                cur.connection.commit()
                print(f"   📈 Inserted {inserted} rows...")
        except Exception as e:
            cur.connection.rollback()
            # Skip bad row, continue
            print(f"   [WARN]  Skipped a row ({e})")
            continue

    cur.connection.commit()
    print(f"  [OK] Inserted {inserted} new rows for account {account_number}")
    return inserted


def main():
    print("🏦 Top-up recent compiled CIBC banking data (no deletes)...")
    with psycopg2.connect(**DB_CONFIG) as conn:
        cur = conn.cursor()
        total = 0
        for code, cfg in ACCOUNTS.items():
            print(f"\n📋 Processing account {code} ({cfg['account_name']})...")
            max_date = get_max_date(cur, cfg['account_number'])
            print(f"  Current max date in DB: {max_date}")
            total += import_new_rows(cur, cfg['file'], cfg['account_number'], cfg['account_name'], max_date)
        print(f"\n🎯 Top-up complete. Total new rows inserted: {total}")


if __name__ == '__main__':
    main()
