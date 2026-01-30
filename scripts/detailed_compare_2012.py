#!/usr/bin/env python3
"""
Detailed comparison of Excel vs Database 2012 invoices
"""

import openpyxl
import psycopg2
import os
from decimal import Decimal
from datetime import datetime

# Load Excel
excel_path = r"L:\limo\reports\WCB_2011_to_Dec_2012.xlsx"
wb = openpyxl.load_workbook(excel_path)
ws = wb.active

excel_data = []
for row in ws.iter_rows(min_row=2, values_only=True):
    if not row[0] or not row[1] or row[1] != 'INVOICE':
        continue
    
    date = row[0]
    ref = str(row[2]) if row[2] else "N/A"
    desc = row[3] if row[3] else ""
    amount = row[4] if row[4] else 0
    
    if isinstance(date, str):
        try:
            date = datetime.strptime(date, "%Y-%m-%d").date()
        except:
            continue
    elif isinstance(date, datetime):
        date = date.date()
    
    if date.year != 2012:
        continue
    
    try:
        amount = Decimal(str(amount).replace(',', '').replace('$', ''))
    except:
        continue
    
    excel_data.append((str(date), ref, amount, desc))

wb.close()

# Load database
conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

cur.execute("""
    SELECT receipt_date::text, source_reference, gross_amount, description
    FROM receipts
    WHERE vendor_name = 'WCB' AND fiscal_year = 2012 AND gross_amount > 0
    ORDER BY receipt_date, source_reference, gross_amount
""")
db_data = [(row[0], row[1] or "N/A", Decimal(str(row[2])), row[3] or "") for row in cur.fetchall()]

print("="*70)
print("DETAILED COMPARISON - 2012 INVOICES")
print("="*70)

# Group by reference number to see duplicates
from collections import defaultdict

excel_by_ref = defaultdict(list)
for date, ref, amt, desc in excel_data:
    excel_by_ref[ref].append((date, amt, desc))

db_by_ref = defaultdict(list)
for date, ref, amt, desc in db_data:
    db_by_ref[ref].append((date, amt, desc))

all_refs = sorted(set(list(excel_by_ref.keys()) + list(db_by_ref.keys())))

for ref in all_refs:
    excel_items = excel_by_ref.get(ref, [])
    db_items = db_by_ref.get(ref, [])
    
    if len(excel_items) != len(db_items):
        print(f"\n⚠️  Reference {ref}: Excel has {len(excel_items)}, DB has {len(db_items)}")
        
        print(f"   EXCEL:")
        for date, amt, desc in excel_items:
            print(f"     {date} | ${amt:>10,.2f} | {desc[:40]}")
        
        print(f"   DATABASE:")
        for date, amt, desc in db_items:
            print(f"     {date} | ${amt:>10,.2f} | {desc[:40]}")

print("\n" + "="*70)
print(f"Excel total: 13 = ${sum(e[2] for e in excel_data):,.2f}")
print(f"DB total:    14 = ${sum(d[2] for d in db_data):,.2f}")
print(f"Difference:  +1 = ${sum(d[2] for d in db_data) - sum(e[2] for e in excel_data):,.2f}")

conn.close()
