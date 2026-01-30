#!/usr/bin/env python3
"""
Compare database 2012 WCB invoices to Excel
"""

import psycopg2
import os
from decimal import Decimal

# Excel data from screenshot (2012 only, excluding 2011-12-30)
excel_invoices = [
    ("2012-03-19", "18254521", Decimal("1126.80"), "installment due"),
    ("2012-04-27", "18394567", Decimal("13.21"), "overdue charge from 04/27/2012"),
    ("2012-05-19", "18394567", Decimal("1126.80"), "installment due"),
    ("2012-06-01", "18457712", Decimal("11.99"), "overdue charge 06/01/2012"),
    ("2012-07-19", "18512376", Decimal("1126.80"), "overdue charge 11.51 06/22/2012"),
    ("2012-08-24", "18604318", Decimal("26.91"), "overdue charge"),
    ("2012-08-30", "18604318", Decimal("470.85"), "2011 actual earnings"),
    ("2012-08-30", "18604318", Decimal("593.81"), "late filing penalty"),
    ("2012-09-19", "18604318", Decimal("42.59"), "installment due"),
    ("2012-10-26", "18681637", Decimal("12.82"), "overdue charges"),
    ("2012-08-03", "18555869", Decimal("14.37"), "overdue charge"),
    ("2012-12-13", "18512376", Decimal("14.54"), "overdue charge"),
    ("2012-06-22", "18512376", Decimal("11.51"), "overdue charge"),
]

excel_total = sum(inv[2] for inv in excel_invoices)

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

cur.execute("""
    SELECT invoice_date, source_reference, gross_amount, description
    FROM receipts
    WHERE vendor_name = 'WCB' AND fiscal_year = 2012 AND gross_amount > 0
    ORDER BY invoice_date, receipt_id
""")
db_invoices = [(str(r[0]), r[1], r[2], r[3]) for r in cur.fetchall()]
db_total = sum(Decimal(str(inv[2])) for inv in db_invoices)

print("="*70)
print("EXCEL vs DATABASE COMPARISON")
print("="*70)

print(f"\nEXCEL: {len(excel_invoices)} invoices = ${excel_total:,.2f}")
print(f"DB:    {len(db_invoices)} invoices = ${db_total:,.2f}")
print(f"Difference: {len(db_invoices) - len(excel_invoices)} invoices, ${db_total - excel_total:,.2f}")

print("\n" + "="*70)
print("MISSING FROM DATABASE (in Excel, not in DB)")
print("="*70)

missing = []
for excel_inv in excel_invoices:
    found = False
    for db_inv in db_invoices:
        if (excel_inv[0] == db_inv[0] and 
            excel_inv[1] == db_inv[1] and 
            abs(excel_inv[2] - Decimal(str(db_inv[2]))) < Decimal("0.01")):
            found = True
            break
    if not found:
        missing.append(excel_inv)

if missing:
    print(f"\nFound {len(missing)} missing invoices:")
    for inv in missing:
        print(f"  {inv[0]} | {inv[1]:12} | ${inv[2]:>10,.2f} | {inv[3][:40]}")
else:
    print("\n✅ All Excel invoices are in database")

print("\n" + "="*70)
print("EXTRA IN DATABASE (in DB, not in Excel)")
print("="*70)

extra = []
for db_inv in db_invoices:
    found = False
    for excel_inv in excel_invoices:
        if (excel_inv[0] == db_inv[0] and 
            excel_inv[1] == db_inv[1] and 
            abs(excel_inv[2] - Decimal(str(db_inv[2]))) < Decimal("0.01")):
            found = True
            break
    if not found:
        extra.append(db_inv)

if extra:
    print(f"\nFound {len(extra)} extra invoices in database:")
    for inv in extra:
        print(f"  {inv[0]} | {inv[1] or 'N/A':12} | ${Decimal(str(inv[2])):>10,.2f} | {(inv[3] or '')[:40]}")
else:
    print("\n✅ No extra invoices in database")

conn.close()
