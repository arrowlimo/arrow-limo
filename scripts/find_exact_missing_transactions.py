#!/usr/bin/env python3
"""
Find the exact 2 missing transactions by comparing Excel vs DB row-by-row
"""

import pandas as pd
import psycopg2
from decimal import Decimal

XLSX_FILE = "L:/limo/data/2013_scotia_transactions_for_editingfinal.xlsx"
SCOTIA_ACCOUNT = '903990106011'

# Load Excel
df_excel = pd.read_excel(XLSX_FILE)
df_excel['date'] = pd.to_datetime(df_excel['date'], errors='coerce')
df_excel = df_excel[df_excel['date'].notna()].sort_values('date').reset_index(drop=True)

# Filter 2014 only
df_2014 = df_excel[df_excel['date'].dt.year == 2014].copy().reset_index(drop=True)

# Load database
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount
    FROM banking_transactions
    WHERE account_number = %s
      AND EXTRACT(YEAR FROM transaction_date) = 2014
    ORDER BY transaction_date, transaction_id
""", (SCOTIA_ACCOUNT,))

db_rows = cur.fetchall()

print("="*80)
print("2014 TRANSACTION COUNTS")
print("="*80)
print(f"Excel: {len(df_2014)} transactions")
print(f"Database: {len(db_rows)} transactions")
print(f"Missing: {len(df_2014) - len(db_rows)} transactions")

# Create signatures for comparison (date + description + amounts)
print("\n" + "="*80)
print("CREATING TRANSACTION SIGNATURES FOR COMPARISON")
print("="*80)

excel_sigs = []
for idx, row in df_2014.iterrows():
    date_str = row['date'].strftime('%Y-%m-%d')
    desc = str(row['Description']).strip()
    debit = float(row['debit/withdrawal']) if pd.notna(row['debit/withdrawal']) else 0.0
    credit = float(row['deposit/credit']) if pd.notna(row['deposit/credit']) else 0.0
    
    sig = f"{date_str}|{desc}|{debit:.2f}|{credit:.2f}"
    excel_sigs.append({
        'signature': sig,
        'date': date_str,
        'description': desc,
        'debit': debit,
        'credit': credit,
        'excel_row': idx
    })

db_sigs = []
for row in db_rows:
    date_str = str(row[0])
    desc = str(row[1]).strip()
    debit = float(row[2]) if row[2] else 0.0
    credit = float(row[3]) if row[3] else 0.0
    
    sig = f"{date_str}|{desc}|{debit:.2f}|{credit:.2f}"
    db_sigs.append({
        'signature': sig,
        'date': date_str,
        'description': desc,
        'debit': debit,
        'credit': credit
    })

# Find missing signatures
excel_sig_set = set([x['signature'] for x in excel_sigs])
db_sig_set = set([x['signature'] for x in db_sigs])
missing_sigs = excel_sig_set - db_sig_set

print(f"\nUnique Excel signatures: {len(excel_sig_set)}")
print(f"Unique DB signatures: {len(db_sig_set)}")
print(f"Missing from DB: {len(missing_sigs)}")

if len(missing_sigs) > 0:
    print("\n" + "="*80)
    print("MISSING TRANSACTIONS (In Excel but NOT in Database)")
    print("="*80)
    
    missing_total_debit = 0
    missing_total_credit = 0
    
    for sig in sorted(missing_sigs):
        # Find the matching Excel row
        matching = [x for x in excel_sigs if x['signature'] == sig]
        if matching:
            m = matching[0]
            print(f"\nExcel Row: {m['excel_row'] + 2}")  # +2 because Excel is 1-indexed and has header
            print(f"Date: {m['date']}")
            print(f"Description: {m['description']}")
            print(f"Debit: ${m['debit']:.2f}")
            print(f"Credit: ${m['credit']:.2f}")
            print(f"Signature: {sig}")
            
            missing_total_debit += m['debit']
            missing_total_credit += m['credit']
    
    print(f"\n{'='*80}")
    print(f"TOTAL MISSING AMOUNTS:")
    print(f"  Debits: ${missing_total_debit:.2f}")
    print(f"  Credits: ${missing_total_credit:.2f}")
    print(f"  Net Impact: ${missing_total_credit - missing_total_debit:.2f}")
    print(f"{'='*80}")

# Check for duplicates in Excel
from collections import Counter
sig_counts = Counter([x['signature'] for x in excel_sigs])
duplicates = {sig: count for sig, count in sig_counts.items() if count > 1}

if duplicates:
    print(f"\n{'='*80}")
    print("WARNING: DUPLICATE SIGNATURES IN EXCEL")
    print(f"{'='*80}")
    for sig, count in duplicates.items():
        print(f"\n{count} copies of: {sig}")

cur.close()
conn.close()

print("\n✅ Analysis complete")
