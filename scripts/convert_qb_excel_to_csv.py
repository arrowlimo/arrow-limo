#!/usr/bin/env python3
"""
Convert QuickBooks Excel export to CSV (GL-compatible)
=====================================================

Takes a QuickBooks "Transaction Detail by Account" / General Ledger Excel export
and converts it into the 9-column CSV layout expected by import_general_ledger.py:

  [0] placeholder, [1] Date, [2] Transaction Type, [3] Ref, [4] Description,
  [5] Account, [6] Debit, [7] Credit, [8] Balance

Usage:
  python scripts/convert_qb_excel_to_csv.py --input "L:\\path\\qb_gl.xlsx" --output "L:\\path\\gl.csv"

Notes:
  - Detects common header variants (Type, Transaction Type, Date, Num/Ref, Name/Memo, Account, Debit, Credit, Balance, Amount)
  - If only Amount is present, generates Debit/Credit based on sign
  - Skips subtotal/blank rows
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd


def normalize_columns(cols):
    return [str(c).strip().lower().replace("\n", " ") for c in cols]


def pick_col(df, options: list[str]) -> Optional[str]:
    cols = normalize_columns(df.columns)
    for opt in options:
        lo = opt.lower()
        for i, c in enumerate(cols):
            if c == lo:
                return df.columns[i]
    # fuzzy contains
    for opt in options:
        lo = opt.lower()
        for i, c in enumerate(cols):
            if lo in c:
                return df.columns[i]
    return None


def to_number(series):
    return pd.to_numeric(series, errors="coerce")


def _read_with_header_detection(xlsx_path: Path, sheet: Optional[str|int]) -> Tuple[pd.DataFrame, Optional[int]]:
    """Read an Excel sheet and try to locate the header row where columns like
    Date / Transaction Type / Account begin. Returns (df, header_row_index).

    Many QuickBooks exports put a title block at the top and the table headers start
    a few rows down. We scan the first ~25 rows to find a row containing key headers.
    """
    # First, read without assigning a header
    raw = pd.read_excel(xlsx_path, sheet_name=sheet, header=None, dtype=str)

    # Normalize helper
    def norm(x):
        x = str(x) if x is not None else ""
        return x.strip().lower()

    header_row = None
    search_rows = min(len(raw), 25)
    key_sets = [
        {"date", "transaction type", "account"},
        {"date", "type", "account"},
        {"date", "name/memo", "account"},
    ]
    for r in range(search_rows):
        row_vals = [norm(v) for v in raw.iloc[r].tolist()]
        row_set = set([v for v in row_vals if v])
        for keys in key_sets:
            if keys.issubset(row_set):
                header_row = r
                break
        if header_row is not None:
            break

    if header_row is not None:
        # Re-read with that row as header
        df = pd.read_excel(xlsx_path, sheet_name=sheet, header=header_row)
        # Drop any top meta rows above header if pandas kept them
        # Ensure the data starts after header row
        df = df.iloc[0:].reset_index(drop=True)
        return df, header_row
    else:
        # Fallback: normal read (first row as header)
        df = pd.read_excel(xlsx_path, sheet_name=sheet)
        return df, None


def convert_gl_excel_to_csv(xlsx_path: Path, out_csv: Path, sheet: Optional[str|int]=0):
    # Prefer the known sheet for QB exports when not provided
    if sheet == 0 or sheet is None:
        preferred_sheets = ["General Ledger", "Transaction Detail by Account", 0]
    else:
        preferred_sheets = [sheet]

    last_err = None
    df = None
    header_row = None
    for sh in preferred_sheets:
        try:
            df, header_row = _read_with_header_detection(xlsx_path, sh)
            sheet = sh  # record which worked
            break
        except Exception as e:
            last_err = e
            continue
    if df is None:
        raise RuntimeError(f"Failed to read Excel file {xlsx_path}: {last_err}")
    # Drop completely empty columns/rows
    df = df.dropna(axis=1, how='all')
    df = df.dropna(axis=0, how='all')

    # Identify columns
    col_date = pick_col(df, ["date", "txn date", "transaction date"])
    col_type = pick_col(df, ["transaction type", "type"]) 
    col_ref  = pick_col(df, ["num", "ref number", "ref no", "reference", "num/ref"]) 
    col_name = pick_col(df, ["name/memo", "name", "memo", "description"]) 
    col_acct = pick_col(df, ["account"]) 
    col_debit  = pick_col(df, ["debit"]) 
    col_credit = pick_col(df, ["credit"]) 
    col_balance = pick_col(df, ["balance", "running balance"]) 
    col_amount  = pick_col(df, ["amount"]) 

    missing = [k for k,v in {
        'date': col_date, 'type': col_type, 'ref': col_ref,
        'desc': col_name, 'account': col_acct
    }.items() if v is None]
    if missing:
        print(f"Warning: Could not find columns: {', '.join(missing)}. Proceeding with what is available.")
    # Informative message about header detection
    if header_row is not None:
        print(f"Info: Detected header row at index {header_row} on sheet '{sheet}'.")
    else:
        print(f"Info: Using first row as header on sheet '{sheet}'.")

    # Build working frame
    w = pd.DataFrame()
    w['Date'] = df[col_date] if col_date else None
    w['Transaction Type'] = df[col_type] if col_type else None
    w['Ref'] = df[col_ref] if col_ref else None
    w['Description'] = df[col_name] if col_name else None
    w['Account'] = df[col_acct] if col_acct else None

    # Amount logic
    if col_debit and col_credit:
        w['Debit'] = to_number(df[col_debit])
        w['Credit'] = to_number(df[col_credit])
    elif col_amount:
        amt = to_number(df[col_amount]).fillna(0)
        # Positive=Debit, Negative=Credit (common QB convention in some exports)
        w['Debit'] = amt.where(amt > 0, 0)
        w['Credit'] = (-amt).where(amt < 0, 0)
    else:
        w['Debit'] = None
        w['Credit'] = None

    w['Balance'] = to_number(df[col_balance]) if col_balance else None

    # Clean rows: drop all-empty essential fields
    essential = ['Date', 'Account', 'Description']
    w = w.dropna(how='all', subset=[c for c in essential if c in w.columns])

    # Remove total/subtotal rows where Date is NaN but Type contains 'total'
    if 'Transaction Type' in w.columns:
        mask_total = w['Transaction Type'].astype(str).str.lower().str.contains('total', na=False)
        w = w[~mask_total]

    # Reorder into the 9-column format for importer
    # [0] placeholder, [1] Date, [2] Transaction Type, [3] Ref, [4] Description, [5] Account, [6] Debit, [7] Credit, [8] Balance
    out = pd.DataFrame()
    out['col0'] = 'QB Excel Import'
    out['Date'] = w.get('Date')
    out['Transaction Type'] = w.get('Transaction Type')
    out['Ref'] = w.get('Ref')
    out['Description'] = w.get('Description')
    out['Account'] = w.get('Account')
    out['Debit'] = w.get('Debit')
    out['Credit'] = w.get('Credit')
    out['Balance'] = w.get('Balance')

    # Write CSV
    out.to_csv(out_csv, index=False)
    print(f"Wrote GL-compatible CSV: {out_csv} (rows: {len(out)})")


def main():
    p = argparse.ArgumentParser(description="Convert QuickBooks Excel export to GL-compatible CSV")
    p.add_argument('--input', required=True, help='Path to Excel export (.xlsx)')
    p.add_argument('--output', required=True, help='Path to output CSV')
    p.add_argument('--sheet', help='Sheet name or index (default 0)')
    args = p.parse_args()

    xlsx = Path(args.input)
    out = Path(args.output)

    if args.sheet is None:
        sheet = 0
    else:
        try:
            sheet = int(args.sheet)
        except ValueError:
            sheet = args.sheet

    convert_gl_excel_to_csv(xlsx, out, sheet=sheet)


if __name__ == '__main__':
    main()
