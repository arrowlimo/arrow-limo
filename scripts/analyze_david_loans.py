#!/usr/bin/env python3
"""Analyze David loans etransfer data from Excel file."""

import pandas as pd
import re
from datetime import datetime

# Read the Excel file
file_path = r'L:\limo\pdf\2012\david loans etransfer some1.xlsx'
df = pd.read_excel(file_path, header=None)

print("="*120)
print("DAVID LOANS ETRANSFER ANALYSIS")
print("="*120)

# The file has no proper headers - first row is data
# Column 0: Date/time string
# Column 1: Amount

print(f"\nTotal transactions: {len(df)}")
print(f"\nRaw columns: {df.columns.tolist()}")
print("\nFirst few rows (raw):")
print(df.head())

# Clean up the data
transactions = []
for idx, row in df.iterrows():
    date_str = str(row[0]).strip()
    amount = row[1]
    
    # Parse the date string
    # Examples: "Tuesday, March 31, 2020 2:10 PM", "Wednesday, May 06, 2020 9:41"
    try:
        # Try to extract date parts using regex
        match = re.search(r'([A-Za-z]+day),\s+([A-Za-z]+)\s+(\d+),\s+(\d{4})', date_str)
        if match:
            month_str = match.group(2)
            day = int(match.group(3))
            year = int(match.group(4))
            
            # Convert month name to number
            month_map = {
                'January': 1, 'February': 2, 'March': 3, 'April': 4,
                'May': 5, 'June': 6, 'July': 7, 'August': 8,
                'September': 9, 'October': 10, 'November': 11, 'December': 12
            }
            month = month_map.get(month_str, 0)
            
            if month > 0:
                date_obj = datetime(year, month, day)
                transactions.append({
                    'date': date_obj,
                    'amount': float(amount),
                    'date_str': date_str
                })
    except Exception as e:
        print(f"Warning: Could not parse row {idx}: {date_str} - {e}")

print("\n" + "="*120)
print(f"PARSED TRANSACTIONS: {len(transactions)}")
print("="*120)

# Sort by date
transactions.sort(key=lambda x: x['date'])

# Summary by year
from collections import defaultdict
by_year = defaultdict(lambda: {'count': 0, 'total': 0})
for t in transactions:
    year = t['date'].year
    by_year[year]['count'] += 1
    by_year[year]['total'] += t['amount']

print("\nSummary by Year:")
print(f"{'Year':6s} | Count | Total Amount | Average")
print("-"*60)
for year in sorted(by_year.keys()):
    data = by_year[year]
    avg = data['total'] / data['count']
    print(f"{year:4d}   | {data['count']:5d} | ${data['total']:>11,.2f} | ${avg:>8.2f}")

total_amount = sum(t['amount'] for t in transactions)
print("-"*60)
print(f"TOTAL  | {len(transactions):5d} | ${total_amount:>11,.2f} | ${total_amount/len(transactions):>8.2f}")

# Summary by month
by_month = defaultdict(lambda: {'count': 0, 'total': 0})
for t in transactions:
    month_key = f"{t['date'].year}-{t['date'].month:02d}"
    by_month[month_key]['count'] += 1
    by_month[month_key]['total'] += t['amount']

print("\n" + "="*120)
print("MONTHLY BREAKDOWN")
print("="*120)
print(f"{'Month':10s} | Count | Total Amount | Average")
print("-"*60)
for month in sorted(by_month.keys()):
    data = by_month[month]
    avg = data['total'] / data['count']
    print(f"{month:8s}   | {data['count']:5d} | ${data['total']:>11,.2f} | ${avg:>8.2f}")

# All transactions chronologically
print("\n" + "="*120)
print("ALL TRANSACTIONS (Chronological)")
print("="*120)
print(f"{'Date':12s} | {'Amount':>10s} | Original Date String")
print("-"*120)
for t in transactions:
    print(f"{t['date'].strftime('%Y-%m-%d'):12s} | ${t['amount']:>9.2f} | {t['date_str'][:50]}")

# Check if these are in banking_transactions
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("\n" + "="*120)
print("MATCHING AGAINST BANKING TRANSACTIONS")
print("="*120)

matched = 0
unmatched = 0

for t in transactions:
    date = t['date']
    amount = t['amount']
    
    # Look for matching credit transaction (loan received)
    # Check date ±3 days, exact amount
    cur.execute("""
        SELECT transaction_id, transaction_date, description, credit_amount, account_number
        FROM banking_transactions
        WHERE transaction_date BETWEEN %s::date - interval '3 days' 
                                   AND %s::date + interval '3 days'
        AND credit_amount = %s
        AND (description ILIKE '%%david%%' 
             OR description ILIKE '%%e-transfer%%'
             OR description ILIKE '%%etransfer%%')
    """, (date, date, amount))
    
    matches = cur.fetchall()
    
    if matches:
        matched += 1
        print(f"\n✓ MATCHED: {date.strftime('%Y-%m-%d')} ${amount:,.2f}")
        for m in matches:
            print(f"  → Banking: {m[1]} ${m[3]:,.2f} {m[4]} - {m[2][:60]}")
    else:
        # Try without name filter
        cur.execute("""
            SELECT transaction_id, transaction_date, description, credit_amount, account_number
            FROM banking_transactions
            WHERE transaction_date BETWEEN %s::date - interval '3 days' 
                                       AND %s::date + interval '3 days'
            AND credit_amount = %s
        """, (date, date, amount))
        
        matches = cur.fetchall()
        if matches:
            matched += 1
            print(f"\n✓ MATCHED (no name): {date.strftime('%Y-%m-%d')} ${amount:,.2f}")
            for m in matches:
                print(f"  → Banking: {m[1]} ${m[3]:,.2f} {m[4]} - {m[2][:60]}")
        else:
            unmatched += 1
            print(f"\n✗ UNMATCHED: {date.strftime('%Y-%m-%d')} ${amount:,.2f}")

print("\n" + "="*120)
print(f"MATCHING SUMMARY: {matched} matched, {unmatched} unmatched")
print("="*120)

conn.close()
