#!/usr/bin/env python3
import psycopg2, os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("="*70)
print("Reference 18254521 in database:")
print("="*70)

cur.execute("""
    SELECT receipt_id, receipt_date, gross_amount, fiscal_year, description
    FROM receipts
    WHERE vendor_name = 'WCB' AND source_reference = '18254521'
    ORDER BY receipt_date
""")

for row in cur.fetchall():
    receipt_id, date, amount, fy, desc = row
    desc_short = (desc[:40] if desc else "")
    print(f"  Receipt {receipt_id} | {date} | ${amount:,.2f} | FY{fy} | {desc_short}")

print(f"\nTotal: {cur.rowcount} records")

# Also check for 686.65 amount
print("\n" + "="*70)
print("All WCB invoices with amount $686.65:")
print("="*70)

cur.execute("""
    SELECT receipt_id, receipt_date, source_reference, fiscal_year, description
    FROM receipts
    WHERE vendor_name = 'WCB' AND ABS(gross_amount - 686.65) < 0.01
    ORDER BY receipt_date
""")

for row in cur.fetchall():
    receipt_id, date, ref, fy, desc = row
    desc_short = (desc[:40] if desc else "")
    print(f"  Receipt {receipt_id} | {date} | {ref or 'N/A':12} | FY{fy or '?'} | {desc_short}")

print(f"\nTotal: {cur.rowcount} records")

conn.close()
