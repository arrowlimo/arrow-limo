#!/usr/bin/env python3
"""
Show which Excel invoices are missing from database
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

excel_invoices = []
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
    
    excel_invoices.append((date, ref, amount, desc))

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
    SELECT source_reference, gross_amount
    FROM receipts
    WHERE vendor_name = 'WCB' AND fiscal_year = 2012 AND gross_amount > 0
""")
db_data = [(row[0] or "N/A", row[1]) for row in cur.fetchall()]

print("="*70)
print("EXCEL INVOICES MISSING FROM DATABASE")
print("="*70)

missing = []
for excel_date, excel_ref, excel_amount, excel_desc in excel_invoices:
    # Try to find match by ref + amount (ignore date)
    found = False
    for db_ref, db_amount in db_data:
        if db_ref == excel_ref and abs(Decimal(str(db_amount)) - excel_amount) < Decimal("0.01"):
            found = True
            break
    
    if not found:
        missing.append((excel_date, excel_ref, excel_amount, excel_desc))

if missing:
    print(f"\nMissing {len(missing)} invoices from Excel:\n")
    for date, ref, amount, desc in missing:
        desc_short = (desc[:40] + "...") if len(desc) > 40 else desc
        print(f"  {date} | {ref:12} | ${amount:>10,.2f} | {desc_short}")
    
    total_missing = sum(m[2] for m in missing)
    print(f"\n  Total missing: ${total_missing:,.2f}")
else:
    print("\n✅ All Excel invoices are in database")

conn.close()
