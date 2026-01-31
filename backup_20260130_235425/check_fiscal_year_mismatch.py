#!/usr/bin/env python3
import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

print("Checking fiscal_year = 2012 records for date mismatches:\n")

cur.execute("""
    SELECT receipt_id, receipt_date, invoice_date, fiscal_year, gross_amount, 
           source_reference, description
    FROM receipts
    WHERE vendor_name = 'WCB' AND fiscal_year = 2012 AND gross_amount > 0
    ORDER BY receipt_date
""")

wrong_year = []
for row in cur.fetchall():
    receipt_id, receipt_date, invoice_date, fiscal_year, amount, ref, desc = row
    actual_year = receipt_date.year if receipt_date else None
    
    desc_short = (desc[:35] + "...") if desc and len(desc) > 35 else (desc or "")
    
    if actual_year and actual_year != 2012:
        wrong_year.append(receipt_id)
        print(f"❌ {receipt_id:6} | {receipt_date} (ACTUAL: {actual_year}) | fy={fiscal_year} | ${amount:>10,.2f} | {ref or 'N/A'}")
    else:
        print(f"✓  {receipt_id:6} | {receipt_date} | fy={fiscal_year} | ${amount:>10,.2f} | {ref or 'N/A'}")

if wrong_year:
    print(f"\n{'='*70}")
    print(f"Found {len(wrong_year)} records with wrong fiscal_year:")
    print(f"IDs: {wrong_year}")
    print("\nFix by updating fiscal_year to match receipt_date.year")
else:
    print(f"\n✅ All fiscal_year = 2012 records have dates in 2012")

conn.close()
