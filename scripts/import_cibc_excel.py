#!/usr/bin/env python3
"""
Import CIBC Excel statements (.xlsx) into banking_transactions.

Supports simple 4-column layouts with headers similar to:
  Date | Description | Debit | Credit

Usage:
  python scripts/import_cibc_excel.py --files "L:/limo/CIBC UPLOADS/cibc May 2017.xlsx" "L:/limo/CIBC UPLOADS/cibc April 2017.xlsx"

Notes:
 - Requires pandas and openpyxl.
 - Creates bank_accounts row if none exists.
 - Generates a source_hash to avoid duplicates.
"""
import os
import hashlib
from decimal import Decimal
import argparse
from datetime import datetime
from dotenv import load_dotenv
import psycopg2
import psycopg2.extras

try:
    import pandas as pd
    import numpy as np
except Exception:
    pd = None


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8', errors='ignore')).hexdigest()


def normalize_amount(x):
    if x is None:
        return Decimal('0')
    if pd is not None and isinstance(x, (float, int)):
        # pandas may give float; handle NaN
        if isinstance(x, float) and (np.isnan(x)):
            return Decimal('0')
        return Decimal(str(x))
    if isinstance(x, (int, float)):
        return Decimal(str(x))
    s = str(x).strip()
    if not s:
        return Decimal('0')
    # Handle parentheses as negatives and common thousand/cur symbols
    neg = False
    if s.startswith('(') and s.endswith(')'):
        neg = True
        s = s[1:-1]
    s = s.replace(',', '').replace('$', '')
    try:
        val = Decimal(s)
        return -val if neg else val
    except Exception:
        return Decimal('0')


def parse_date(s):
    if isinstance(s, datetime):
        return s.date()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y", "%b %d, %Y"):
        try:
            return datetime.strptime(str(s).strip(), fmt).date()
        except Exception:
            continue
    # Let pandas parse as last resort
    try:
        return pd.to_datetime(s).date()
    except Exception:
        raise ValueError(f"Unparsable date: {s}")


def ensure_bank_account(cur) -> int:
    cur.execute("SELECT bank_id FROM bank_accounts ORDER BY bank_id LIMIT 1")
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        """
        INSERT INTO bank_accounts (account_name, institution_name, account_type, notes)
        VALUES ('Primary Checking', 'CIBC', 'checking', 'Auto-created by import_cibc_excel')
        RETURNING bank_id
        """
    )
    return cur.fetchone()[0]


def import_file(cur, bank_id: int, path: str, account_number: str) -> tuple[int, int]:
    xls = pd.ExcelFile(path, engine='openpyxl')
    imported = 0
    skipped = 0
    for sheet in xls.sheet_names:
        df = xls.parse(sheet_name=sheet, header=None)
        # If the first row looks like headers (contains strings like Date/Description), promote them
        first = df.iloc[0].tolist() if df.shape[0] > 0 else []
        looks_like_header = any(isinstance(x, str) and ('date' in x.lower() or 'descr' in x.lower() or 'memo' in x.lower()) for x in first)
        if looks_like_header:
            headers = [str(x).strip() if isinstance(x, str) else f"col{i}" for i, x in enumerate(first)]
            df = df.iloc[1:].reset_index(drop=True)
            df.columns = headers
        else:
            # Assume 4 columns Date|Description|Debit|Credit as per preview
            df.columns = ['Date', 'Description', 'Debit', 'Credit'][:df.shape[1]]
        # Try to find columns by common names
        coerced_cols = [str(c) for c in df.columns]
        cols = {c.lower().strip(): c for c in coerced_cols}
        date_col = 'Date' if 'Date' in df.columns else cols.get('date') or next((c for c in df.columns if isinstance(c, str) and 'date' in c.lower()), None)
        desc_col = 'Description' if 'Description' in df.columns else cols.get('description') or next((c for c in df.columns if isinstance(c, str) and ('memo' in c.lower() or 'description' in c.lower() or 'details' in c.lower() or 'transaction' in c.lower())), None)
        debit_col = 'Debit' if 'Debit' in df.columns else next((c for c in df.columns if isinstance(c, str) and ('debit' in c.lower() or 'withdrawal' in c.lower() or 'debits' in c.lower() or 'withdrawals' in c.lower())), None)
        credit_col = 'Credit' if 'Credit' in df.columns else next((c for c in df.columns if isinstance(c, str) and ('credit' in c.lower() or 'deposit' in c.lower() or 'credits' in c.lower() or 'deposits' in c.lower())), None)

        # Fallback: if only 3 columns assume Date|Description|Amount
        amount_col = None
        if (debit_col is None and credit_col is None) and df.shape[1] >= 3:
            amount_col = df.columns[2]

        if not date_col or not desc_col:
            # skip this sheet
            continue

        total_rows = 0
        empty_rows = 0
        bad_date_or_desc = 0
        errors = 0
        for idx, row in df.iterrows():
            try:
                dt = parse_date(row.get(date_col))
                desc = str(row.get(desc_col, '')).strip()
                if amount_col is not None:
                    amt = normalize_amount(row.get(amount_col))
                    # Positive as credit, negative as debit
                    debit = -amt if amt < 0 else Decimal('0')
                    credit = amt if amt > 0 else Decimal('0')
                else:
                    debit = normalize_amount(row.get(debit_col)) if debit_col else Decimal('0')
                    credit = normalize_amount(row.get(credit_col)) if credit_col else Decimal('0')

                total_rows += 1
                # Skip lines with no amounts or missing date/desc
                if not desc or dt is None:
                    bad_date_or_desc += 1
                    continue
                if (debit == 0 and credit == 0):
                    empty_rows += 1
                    continue

                transaction_hash = sha256(f"{dt}|{desc}|{debit}|{credit}|{os.path.basename(path)}|{sheet}|{idx}")
                cur.execute("SELECT 1 FROM banking_transactions WHERE transaction_hash = %s", (transaction_hash,))
                if cur.fetchone():
                    skipped += 1
                    continue

                # Light classification
                desc_up = desc.upper()
                if 'E-TRANSFER' in desc_up or 'INTERAC' in desc_up:
                    ttype = 'ETRANSFER'
                elif 'ATM' in desc_up:
                    ttype = 'ATM_WITHDRAWAL'
                elif 'POS' in desc_up or 'RETAIL PURCHASE' in desc_up:
                    ttype = 'POS_PURCHASE'
                elif 'FEE' in desc_up:
                    ttype = 'BANK_FEE'
                elif 'INTEREST' in desc_up:
                    ttype = 'INTEREST'
                else:
                    ttype = 'OTHER'

                # Insert using current schema columns (no transaction_type)
                cur.execute(
                    """
                    INSERT INTO banking_transactions (
                        bank_id, account_number, transaction_date, description,
                        debit_amount, credit_amount,
                        source_file, transaction_hash
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s
                    )
                    """,
                    (
                        bank_id, account_number, dt, desc, debit, credit,
                        os.path.basename(path), transaction_hash
                    ),
                )
                imported += 1
            except Exception as e:
                errors += 1
                # Show a compact error line for debugging
                try:
                    print(f"    row {idx}: error {str(e)[:120]} :: desc={str(row.get(desc_col,''))[:60]}")
                except Exception:
                    print(f"    row {idx}: error {str(e)[:120]}")
                continue

    # Debug summary per sheet
    print(f"  Sheet {sheet}: rows={total_rows}, inserted_so_far={imported}, empty={empty_rows}, bad_date_or_desc={bad_date_or_desc}, errors={errors}")

    return imported, skipped


def main():
    load_dotenv('l:/limo/.env'); load_dotenv()
    ap = argparse.ArgumentParser(description='Import CIBC Excel statements into banking_transactions')
    ap.add_argument('--files', nargs='+', required=True, help='Paths to .xlsx/.xlsm files to import')
    ap.add_argument('--account', required=True, help='Bank account number to tag these transactions with (e.g., 0228362)')
    args = ap.parse_args()

    if pd is None:
        print('pandas is not installed. Install with: pip install pandas openpyxl')
        return

    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***'),
    )
    cur = conn.cursor()
    try:
        bank_id = ensure_bank_account(cur)
        total_imported = 0
        total_skipped = 0
        for path in args.files:
            if not os.path.exists(path):
                print(f"Missing file: {path}")
                continue
            try:
                imp, sk = import_file(cur, bank_id, path, args.account)
                # Update inserted rows with account number; or include in insert below
                conn.commit()
            except Exception as e:
                conn.rollback()
                print(f"Error importing {path}: {e}")
                continue
            print(f"Imported {imp}, skipped {sk} from {path}")
            total_imported += imp
            total_skipped += sk
        print(f"\nSummary: Imported {total_imported}, skipped {total_skipped}")
    finally:
        cur.close(); conn.close()


if __name__ == '__main__':
    main()
