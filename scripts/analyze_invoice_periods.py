#!/usr/bin/env python3
"""
What invoices exist before the first payment (2012-03-19)?
These should be linked to Receipt 145297 ($686.65)
"""

import psycopg2
import os
from decimal import Decimal

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("\n" + "="*70)
print("INVOICES DATED BEFORE FIRST PAYMENT (2012-03-19)")
print("="*70)
print("\nThese should likely be linked to Receipt 145297 ($686.65):")
print()

cur.execute("""
    SELECT receipt_id, source_reference, receipt_date, gross_amount, 
           description, vendor_name
    FROM receipts
    WHERE vendor_name IN ('WCB', 'WCB ALBERTA')
      AND gross_amount > 0
      AND receipt_date < '2012-03-19'
    ORDER BY receipt_date
""")

total_before = Decimal('0')
for row in cur.fetchall():
    receipt_id, ref, date, amount, desc, vendor = row
    print(f"  Receipt {receipt_id:6} | Ref {ref} | {date} | ${amount:>10,.2f}")
    total_before += amount

print(f"\n  TOTAL BEFORE 2012-03-19: ${total_before:,.2f}")
print(f"  First Payment (145297):  $         686.65")
print(f"  Match? {abs(total_before - Decimal('686.65')) < Decimal('0.01')}")

print(f"\n{'='*70}")
print("INVOICES BETWEEN PAYMENTS")
print(f"{'='*70}")

# Check between each payment
date_ranges = [
    ("2012-03-19", "2012-08-28", "Receipt 145297 -> TX 69282"),
    ("2012-08-28", "2012-11-27", "TX 69282 -> TX 69587"),
    ("2012-11-27", "2013-01-01", "TX 69587 -> end"),
]

for start_date, end_date, label in date_ranges:
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
        FROM receipts
        WHERE vendor_name IN ('WCB', 'WCB ALBERTA')
          AND gross_amount > 0
          AND receipt_date > %s AND receipt_date <= %s
    """, (start_date, end_date))
    
    count, total = cur.fetchone()
    total = total or Decimal('0')
    print(f"\n{label}")
    print(f"  Between {start_date} and {end_date}")
    print(f"  Count: {count}, Total: ${total:,.2f}")

conn.close()
