#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Export monthly Excel Cash EXPENSE worksheets for 2012 from the parsed QB register CSV.

Inputs:
- exports/banking/2012_qb_register_parsed.csv (created by parse_quickbooks_register_text.py)

Outputs:
- exports/cash_expenses/2012_MM_cash_expenses.xlsx for MM=01..12

Heuristics for 'cash expense' inclusion:
- Include rows with a debit amount (money out)
- Include common payment types: Cheque, DD, Online, Auto, WD, ETSFR, ETSF, TSF
- Exclude obvious transfers and internal moves: names containing
  ['Arrow Limousine', 'CIBC Bank', 'Scotia Bank Main', 'Shareholder Loans']
  (Service charges are kept as expenses.)

Columns in output:
- Date, Account, Type, Num, Name, Memo, Amount (debit), Balance
"""

import os
import math
import pandas as pd

IN_CSV = os.path.join('exports', 'banking', '2012_qb_register_parsed.csv')
OUT_DIR = os.path.join('exports', 'cash_expenses')


def load_parsed() -> pd.DataFrame:
    df = pd.read_csv(IN_CSV, dtype=str).fillna('')
    # Normalize dates
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
    # Normalize amount columns to numeric
    for col in ('debit', 'credit', 'balance'):
        if col in df.columns:
            df[col] = (
                df[col]
                .str.replace(',', '', regex=False)
                .str.replace('(', '-', regex=False)
                .str.replace(')', '', regex=False)
            )
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


def is_cash_expense_row(row: pd.Series) -> bool:
    # Amount going out
    amt = row.get('debit', 0.0)
    if not (isinstance(amt, (int, float)) and not math.isnan(amt) and amt > 0):
        return False
    t = (row.get('type', '') or '').lower()
    allowed_types = {'cheque', 'dd', 'online', 'auto', 'wd', 'etsfr', 'etsf', 'tsf'}
    if t not in allowed_types:
        # Some register lines may show General Journal for expenses (e.g., service charge entries)
        if t != 'general journal':
            return False
    name = (row.get('name', '') or '').lower()
    exclude_names = ['arrow limousine', 'cibc bank', 'scotia bank main', 'shareholder loans']
    if any(x in name for x in exclude_names):
        return False
    return True


def export_monthly_excels(df: pd.DataFrame) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    # Filter year 2012
    df2012 = df[df['date'].dt.year == 2012].copy()
    df2012 = df2012[df2012.apply(is_cash_expense_row, axis=1)].copy()

    # Prepare neat columns
    df2012['Amount'] = df2012['debit']
    out_cols = ['date', 'account', 'type', 'num', 'name', 'memo', 'Amount', 'balance']
    present_cols = [c for c in out_cols if c in df2012.columns]
    df2012 = df2012[present_cols].rename(columns={
        'date': 'Date',
        'account': 'Account',
        'type': 'Type',
        'num': 'Num',
        'name': 'Payee',
        'memo': 'Memo',
        'balance': 'Balance',
    })

    # Group by month
    df2012['Month'] = df2012['Date'].dt.month
    for m in range(1, 13):
        month_df = df2012[df2012['Month'] == m].copy()
        # Sort by date then check number
        month_df = month_df.sort_values(by=['Date', 'Num'], na_position='last')
        # Drop helper column
        if 'Month' in month_df.columns:
            month_df = month_df.drop(columns=['Month'])
        out_path = os.path.join(OUT_DIR, f'2012_{m:02d}_cash_expenses.xlsx')
        # Write to Excel
        with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
            month_df.to_excel(writer, index=False, sheet_name=f'2012-{m:02d}')
        print(f'Wrote {out_path}: {len(month_df)} rows')


def main() -> None:
    df = load_parsed()
    export_monthly_excels(df)


if __name__ == '__main__':
    main()
