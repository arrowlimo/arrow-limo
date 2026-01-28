#!/usr/bin/env python3
"""
Get exact invoice/payment list from Excel and compare to database
"""

import openpyxl
import psycopg2
import os
from decimal import Decimal
from datetime import datetime

excel_path = r"L:\limo\reports\WCB_2011_to_Dec_2012.xlsx"
wb = openpyxl.load_workbook(excel_path)
ws = wb.active

# Read all data rows
excel_data = []
for row in ws.iter_rows(min_row=2, values_only=True):
    if not row[0]:  # Skip if no date
        continue
    
    date = row[0]
    row_type = row[1]
    ref = str(row[2]) if row[2] else "N/A"
    desc = row[3] if row[3] else ""
    amount = row[4] if row[4] else 0
    
    # Parse date if string
    if isinstance(date, str):
        try:
            date = datetime.strptime(date, "%Y-%m-%d").date()
        except:
            continue
    elif isinstance(date, datetime):
        date = date.date()
    
    # Convert amount
    try:
        amount = Decimal(str(amount).replace(',', '').replace('$', ''))
    except:
        amount = Decimal('0')
    
    excel_data.append((date, row_type, ref, desc, amount))

wb.close()

# Separate by year
data_2011 = [d for d in excel_data if d[0].year == 2011]
data_2012 = [d for d in excel_data if d[0].year == 2012]

invoices_2012 = [d for d in data_2012 if d[1] == 'INVOICE']
payments_2012 = [d for d in data_2012 if d[1] == 'PAYMENT' or d[1] == 'refunded']

print("="*70)
print("EXCEL: 2012 WCB INVOICES")
print("="*70)

total_inv = Decimal('0')
for i, inv in enumerate(invoices_2012, 1):
    date, typ, ref, desc, amount = inv
    desc_display = (desc[:45] + "...") if len(desc) > 45 else desc
    print(f"{i:2}. {date} | {ref:12} | ${amount:>10,.2f} | {desc_display}")
    total_inv += amount

print(f"\n   Total: {len(invoices_2012)} invoices = ${total_inv:,.2f}")

print(f"\n{'='*70}")
print("EXCEL: 2012 WCB PAYMENTS")
print("="*70)

total_pmt = Decimal('0')
for i, pmt in enumerate(payments_2012, 1):
    date, typ, ref, desc, amount = pmt
    desc_display = (desc[:45] + "...") if len(desc) > 45 else desc
    print(f"{i:2}. {date} | {ref:12} | ${amount:>10,.2f} | {desc_display}")
    total_pmt += amount

print(f"\n   Total: {len(payments_2012)} payments = ${total_pmt:,.2f}")

balance = total_inv - total_pmt
print(f"\n2012 Balance: ${total_inv:,.2f} - ${total_pmt:,.2f} = ${balance:,.2f}")

# Now compare to database
print(f"\n{'='*70}")
print("DATABASE: 2012 WCB INVOICES")
print("="*70)

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
    FROM receipts
    WHERE vendor_name = 'WCB' AND fiscal_year = 2012 AND gross_amount > 0
""")
db_count, db_total = cur.fetchone()

print(f"\nDatabase: {db_count} invoices = ${db_total:,.2f}")
print(f"Excel:    {len(invoices_2012)} invoices = ${total_inv:,.2f}")
print(f"Difference: {db_count - len(invoices_2012)} invoices, ${db_total - total_inv:+,.2f}")

conn.close()
