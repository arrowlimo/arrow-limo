#!/usr/bin/env python3
"""
Check the full date range of all invoices in the Fibrenew Excel file.
"""

import pandas as pd
from datetime import datetime

EXCEL_FILE = r'L:\limo\pdf\2012\fibrenew.xlsx'

def parse_date(val):
    if pd.isna(val):
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        for fmt in ['%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%d']:
            try:
                return datetime.strptime(val.strip(), fmt).date()
            except:
                continue
    return None

# Read Excel file
df = pd.read_excel(EXCEL_FILE, header=None)

print("="*80)
print("FIBRENEW EXCEL FILE - FULL DATE RANGE ANALYSIS")
print("="*80)
print(f"\nTotal rows in file: {len(df)}")
print(f"Total columns: {len(df.columns)}")

# Check all rows
all_dates = []
invoice_rows = []
payment_rows = []
statement_rows = []
other_rows = []

for idx, row in df.iterrows():
    col0 = str(row[0]).strip()
    col1 = str(row[1]).strip() if not pd.isna(row[1]) else ''
    
    if col0.lower() == 'inv':
        continue  # Header row
    
    parsed_date = parse_date(row[1])
    
    if col0.lower() == 'pmt':
        payment_rows.append((idx, parsed_date, row[2], row[3] if len(row) > 3 else None))
        if parsed_date:
            all_dates.append(parsed_date)
    elif col0.lower() == 'statement':
        statement_rows.append((idx, parsed_date, row[2], row[3] if len(row) > 3 else None))
        if parsed_date:
            all_dates.append(parsed_date)
    elif col0 and col0 not in ['nan', ''] and not 'balance' in col1.lower():
        # Likely invoice
        invoice_rows.append((idx, col0, parsed_date, row[2], row[3] if len(row) > 3 else None))
        if parsed_date:
            all_dates.append(parsed_date)
    else:
        if not pd.isna(row[0]) or not pd.isna(row[1]):
            other_rows.append((idx, col0, col1, row[2] if len(row) > 2 else None))

print(f"\nRow breakdown:")
print(f"  Invoice rows: {len(invoice_rows)}")
print(f"  Payment rows: {len(payment_rows)}")
print(f"  Statement rows: {len(statement_rows)}")
print(f"  Other rows: {len(other_rows)}")

if all_dates:
    all_dates.sort()
    print(f"\nDate range: {all_dates[0]} to {all_dates[-1]}")
    print(f"Total entries with dates: {len(all_dates)}")

# Show invoice date range
invoice_dates = [d for _, _, d, _, _ in invoice_rows if d]
if invoice_dates:
    invoice_dates.sort()
    print(f"\nInvoice date range: {invoice_dates[0]} to {invoice_dates[-1]}")
    
    # Group by year
    by_year = {}
    for _, inv_num, date, amt, notes in invoice_rows:
        if date:
            year = date.year
            if year not in by_year:
                by_year[year] = []
            by_year[year].append((inv_num, date, amt))
    
    print(f"\nInvoices by year:")
    for year in sorted(by_year.keys()):
        print(f"  {year}: {len(by_year[year])} invoices")

# Show payment date range
payment_dates = [d for _, d, _, _ in payment_rows if d]
if payment_dates:
    payment_dates.sort()
    print(f"\nPayment date range: {payment_dates[0]} to {payment_dates[-1]}")
    
    # Group by year
    by_year = {}
    for _, date, amt, notes in payment_rows:
        if date:
            year = date.year
            if year not in by_year:
                by_year[year] = []
            by_year[year].append((date, amt))
    
    print(f"\nPayments by year:")
    for year in sorted(by_year.keys()):
        total = sum(float(amt) if not pd.isna(amt) else 0 for _, amt in by_year[year])
        print(f"  {year}: {len(by_year[year])} payments (${abs(total):,.2f})")

# Show last 10 rows of file
print(f"\n{'='*80}")
print("LAST 10 ROWS OF FILE:")
print(f"{'='*80}")
for idx in range(max(0, len(df) - 10), len(df)):
    row = df.iloc[idx]
    print(f"Row {idx}: {row[0]} | {row[1]} | {row[2]} | {row[3] if len(row) > 3 else ''}")

# Check for 2016 data
print(f"\n{'='*80}")
print("SEARCHING FOR 2016 DATA:")
print(f"{'='*80}")

has_2016 = False
for idx, row in df.iterrows():
    parsed_date = parse_date(row[1])
    if parsed_date and parsed_date.year == 2016:
        print(f"Row {idx}: {row[0]} | {row[1]} | {row[2]} | {row[3] if len(row) > 3 else ''}")
        has_2016 = True

if not has_2016:
    print("No 2016 data found in file.")
