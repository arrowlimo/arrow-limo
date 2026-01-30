#!/usr/bin/env python3
"""
Find database invoices NOT in Excel
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

excel_invoices = set()
for row in ws.iter_rows(min_row=2, values_only=True):
    if not row[0] or not row[1] or row[1] != 'INVOICE':
        continue
    
    date = row[0]
    ref = str(row[2]) if row[2] else "N/A"
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
    
    # Create key: ref + amount (ignore date)
    key = (ref, amount)
    excel_invoices.add(key)

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
    SELECT receipt_id, receipt_date, source_reference, gross_amount, description
    FROM receipts
    WHERE vendor_name = 'WCB' AND fiscal_year = 2012 AND gross_amount > 0
    ORDER BY receipt_date
""")

print("="*70)
print("DATABASE INVOICES NOT IN EXCEL")
print("="*70)

extra = []
for row in cur.fetchall():
    receipt_id, date, ref, amount, desc = row
    ref = ref or "N/A"
    key = (ref, Decimal(str(amount)))
    
    if key not in excel_invoices:
        extra.append((receipt_id, date, ref, amount, desc))

if extra:
    print(f"\nFound {len(extra)} extra invoices in database:\n")
    for receipt_id, date, ref, amount, desc in extra:
        desc_short = (desc[:40] + "...") if desc and len(desc) > 40 else (desc or "")
        print(f"  Receipt {receipt_id} | {date} | {ref:12} | ${amount:>10,.2f} | {desc_short}")
    
    total_extra = sum(e[3] for e in extra)
    print(f"\n  Total extra: ${total_extra:,.2f}")
else:
    print("\n✅ No extra invoices in database")

conn.close()
