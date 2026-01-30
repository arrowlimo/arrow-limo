#!/usr/bin/env python3
"""
Restore 3 WCB invoices that were incorrectly deleted
"""

import psycopg2
import os
from datetime import date

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

# Invoices to restore from Excel
invoices = [
    {
        'date': date(2012, 3, 19),
        'ref': '18254521',
        'amount': 1126.80,
        'desc': 'installment due',
        'category': 'WCB'
    },
    {
        'date': date(2012, 7, 19),
        'ref': '18512376',
        'amount': 1126.80,
        'desc': 'overdue charge 11.51 06/22/2012,overdue charge 64.29 06/22/2012,installment due 1051.00 07/01/2012',
        'category': 'WCB-fees/penalties'
    },
    {
        'date': date(2012, 12, 13),
        'ref': '18512376',
        'amount': 14.54,
        'desc': 'overdue charge',
        'category': 'WCB-fees/penalties'
    }
]

print("="*70)
print("RESTORING 3 DELETED WCB INVOICES")
print("="*70)

for inv in invoices:
    # Check if already exists
    cur.execute("""
        SELECT receipt_id FROM receipts
        WHERE vendor_name = 'WCB' 
        AND source_reference = %s 
        AND ABS(gross_amount - %s) < 0.01
        AND receipt_date = %s
    """, (inv['ref'], inv['amount'], inv['date']))
    
    if cur.fetchone():
        print(f"  ⚠️  Already exists: {inv['ref']} ({inv['date']}) ${inv['amount']:,.2f}")
        continue
    
    # Insert
    cur.execute("""
        INSERT INTO receipts (
            receipt_date, vendor_name, source_reference, 
            gross_amount, category, fiscal_year, 
            payment_method, description, invoice_date
        ) VALUES (
            %s, 'WCB', %s,
            %s, 'Administrative', 2012,
            'unknown', %s, %s
        )
        RETURNING receipt_id
    """, (inv['date'], inv['ref'], inv['amount'], inv['desc'], inv['date']))
    
    receipt_id = cur.fetchone()[0]
    print(f"  ✅ Created: Receipt {receipt_id} | {inv['ref']} | {inv['date']} | ${inv['amount']:,.2f}")

conn.commit()

# Verify final count
cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE vendor_name = 'WCB' AND fiscal_year = 2012 AND gross_amount > 0
""")
count, total = cur.fetchone()

print(f"\n✅ Final 2012 WCB invoices: {count} = ${total:,.2f}")
print(f"   Excel target: 13 invoices = $4,593.00")

if count == 13 and abs(total - 4593.00) < 0.01:
    print("   🎉 DATABASE MATCHES EXCEL!")

conn.close()
