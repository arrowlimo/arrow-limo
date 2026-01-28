#!/usr/bin/env python3
"""
Find duplicate/extra invoices in database that aren't in Excel
"""

import openpyxl
import psycopg2
import os
from decimal import Decimal
from datetime import datetime

# Load Excel data
excel_path = r"L:\limo\reports\WCB_2011_to_Dec_2012.xlsx"
wb = openpyxl.load_workbook(excel_path)
ws = wb.active

excel_invoices_2012 = []
for row in ws.iter_rows(min_row=2, values_only=True):
    if not row[0] or not row[1]:
        continue
    
    date = row[0]
    row_type = row[1]
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
    
    if row_type != 'INVOICE':
        continue
    
    try:
        amount = Decimal(str(amount).replace(',', '').replace('$', ''))
    except:
        amount = Decimal('0')
    
    excel_invoices_2012.append((date, ref, amount))

wb.close()

# Load database data
conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

cur.execute("""
    SELECT receipt_id, receipt_date, source_reference, gross_amount, description
    FROM receipts
    WHERE vendor_name = 'WCB' 
      AND fiscal_year = 2012 
      AND gross_amount > 0
      AND banking_transaction_id IS NULL
      AND NOT EXISTS (
          SELECT 1 FROM banking_receipt_matching_ledger brml
          WHERE brml.receipt_id = receipts.receipt_id
      )
    ORDER BY receipt_date, receipt_id
""")

db_invoices = []
for row in cur.fetchall():
    receipt_id, date, ref, amount, desc = row
    db_invoices.append((receipt_id, date, ref or "N/A", amount, desc))

print("="*70)
print("FINDING DUPLICATES IN DATABASE")
print("="*70)

# Find database records NOT in Excel
duplicates = []
for db_inv in db_invoices:
    receipt_id, db_date, db_ref, db_amount, db_desc = db_inv
    
    # Try to find match in Excel
    found = False
    for excel_date, excel_ref, excel_amount in excel_invoices_2012:
        if (db_date == excel_date and 
            db_ref == excel_ref and 
            abs(db_amount - excel_amount) < Decimal("0.01")):
            found = True
            break
    
    if not found:
        duplicates.append(db_inv)

if duplicates:
    print(f"\nFound {len(duplicates)} extra/duplicate invoices in database:\n")
    for dup in duplicates:
        receipt_id, date, ref, amount, desc = dup
        desc_short = (desc[:35] + "...") if desc and len(desc) > 35 else (desc or "")
        print(f"  {receipt_id:6} | {date} | {ref:12} | ${amount:>10,.2f} | {desc_short}")
    
    dup_ids = [d[0] for d in duplicates]
    dup_total = sum(d[3] for d in duplicates)
    
    print(f"\n  IDs to delete: {dup_ids}")
    print(f"  Total to remove: ${dup_total:,.2f}")
    
    print("\nDelete these duplicates? (yes/no): ", end="")
    confirm = input()
    if confirm.lower() == 'yes':
        cur.execute("""
            DELETE FROM receipts
            WHERE receipt_id = ANY(%s)
        """, (dup_ids,))
        conn.commit()
        print(f"\n✅ Deleted {cur.rowcount} duplicate invoices")
        
        # Show new totals
        cur.execute("""
            SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
            FROM receipts
            WHERE vendor_name = 'WCB' AND fiscal_year = 2012 AND gross_amount > 0
        """)
        count, total = cur.fetchone()
        print(f"\nNew 2012 totals: {count} invoices = ${total:,.2f}")
    else:
        print("\n❌ Cancelled")
else:
    print("\n✅ No duplicates found - database matches Excel")

conn.close()
