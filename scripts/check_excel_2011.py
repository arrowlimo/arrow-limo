#!/usr/bin/env python3
"""
Check 2011 transactions in Excel
"""

import openpyxl
from datetime import datetime
from decimal import Decimal

excel_path = r"L:\limo\reports\WCB_2011_to_Dec_2012.xlsx"
wb = openpyxl.load_workbook(excel_path)
ws = wb.active

print("="*70)
print("2011 TRANSACTIONS IN EXCEL")
print("="*70)

invoices_2011 = []
payments_2011 = []

for row in ws.iter_rows(min_row=2, values_only=True):
    if not row[0] or not row[1]:
        continue
    
    date = row[0]
    trans_type = row[1]
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
    
    if date.year != 2011:
        continue
    
    try:
        amount = Decimal(str(amount).replace(',', '').replace('$', ''))
    except:
        continue
    
    if trans_type == 'INVOICE':
        invoices_2011.append((date, ref, amount, desc))
    elif trans_type == 'PAYMENT':
        payments_2011.append((date, ref, amount, desc))

print(f"\n2011 INVOICES ({len(invoices_2011)}):")
for date, ref, amount, desc in invoices_2011:
    desc_short = (desc[:50] + "...") if len(desc) > 50 else desc
    print(f"  {date} | {ref:12} | ${amount:>10,.2f} | {desc_short}")

if invoices_2011:
    total = sum(i[2] for i in invoices_2011)
    print(f"  Total: ${total:,.2f}")

print(f"\n2011 PAYMENTS ({len(payments_2011)}):")
for date, ref, amount, desc in payments_2011:
    desc_short = (desc[:50] + "...") if len(desc) > 50 else desc
    print(f"  {date} | {ref:12} | ${amount:>10,.2f} | {desc_short}")

if payments_2011:
    total = sum(p[2] for p in payments_2011)
    print(f"  Total: ${total:,.2f}")

if invoices_2011 or payments_2011:
    inv_total = sum(i[2] for i in invoices_2011)
    pay_total = sum(p[2] for p in payments_2011)
    balance = inv_total + pay_total  # payments are negative
    print(f"\n2011 Balance: ${inv_total:,.2f} + ${pay_total:,.2f} = ${balance:,.2f}")

wb.close()
