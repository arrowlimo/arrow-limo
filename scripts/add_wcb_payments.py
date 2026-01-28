#!/usr/bin/env python3
"""
Add 3 WCB payments from Excel
"""

import psycopg2, os
from datetime import date

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

# Check if payments already exist
cur.execute("""
    SELECT receipt_id, receipt_date, source_reference, gross_amount
    FROM receipts
    WHERE vendor_name = 'WCB' 
    AND source_reference IN ('18604318', '18714897')
    AND fiscal_year = 2012
    ORDER BY receipt_date
""")

existing = cur.fetchall()
if existing:
    print("Existing receipts with payment references:")
    for row in existing:
        print(f"  {row[0]:6} | {row[1]} | {row[2]:12} | ${row[3]:>10,.2f}")

# Payments to add from Excel
payments = [
    {
        'date': date(2012, 8, 28),
        'ref': '18604318',
        'amount': -3446.02,
        'desc': 'WCB payment'
    },
    {
        'date': date(2012, 11, 26),
        'ref': '18714897',
        'amount': -553.17,
        'desc': 'wcb payment'
    },
    {
        'date': date(2012, 11, 27),
        'ref': '18714897',
        'amount': -593.81,
        'desc': 'wcb waived late filing penalty'
    }
]

print("\n" + "="*70)
print("ADDING 3 WCB PAYMENTS FROM EXCEL")
print("="*70)

for pmt in payments:
    # Check if already exists
    cur.execute("""
        SELECT receipt_id FROM receipts
        WHERE vendor_name = 'WCB'
        AND source_reference = %s
        AND receipt_date = %s
        AND ABS(gross_amount - %s) < 0.01
    """, (pmt['ref'], pmt['date'], pmt['amount']))
    
    if cur.fetchone():
        print(f"  ⚠️  Already exists: {pmt['date']} | {pmt['ref']} | ${pmt['amount']:,.2f}")
        continue
    
    # Insert payment
    cur.execute("""
        INSERT INTO receipts (
            receipt_date, vendor_name, source_reference,
            gross_amount, category, fiscal_year,
            payment_method, description
        ) VALUES (
            %s, 'WCB', %s,
            %s, 'Administrative', 2012,
            'unknown', %s
        )
        RETURNING receipt_id
    """, (pmt['date'], pmt['ref'], pmt['amount'], pmt['desc']))
    
    receipt_id = cur.fetchone()[0]
    print(f"  ✅ Created: Receipt {receipt_id} | {pmt['date']} | {pmt['ref']} | ${pmt['amount']:,.2f}")

conn.commit()

# Verify balance
cur.execute("""
    SELECT 
        SUM(CASE WHEN gross_amount > 0 THEN gross_amount ELSE 0 END) as invoices,
        SUM(CASE WHEN gross_amount < 0 THEN gross_amount ELSE 0 END) as payments
    FROM receipts
    WHERE vendor_name = 'WCB' AND fiscal_year = 2012
""")
invoices, payments = cur.fetchone()

balance = (invoices or 0) + (payments or 0)

print("\n" + "="*70)
print(f"Invoices:  ${invoices or 0:,.2f}")
print(f"Payments:  ${payments or 0:,.2f}")
print(f"Balance:   ${balance:,.2f}")
print("="*70)

if abs(balance) < 0.01:
    print("\n✅ ACCOUNT BALANCED! Balance = $0.00")
else:
    print(f"\n⚠️  Balance = ${balance:,.2f}")

conn.close()
