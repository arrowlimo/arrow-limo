#!/usr/bin/env python3
import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("="*70)
print("ALL WCB RECORDS BY YEAR")
print("="*70)

cur.execute("""
    SELECT EXTRACT(YEAR FROM receipt_date) as year, 
           COUNT(*), 
           SUM(gross_amount)
    FROM receipts
    WHERE vendor_name = 'WCB' AND gross_amount > 0
    GROUP BY EXTRACT(YEAR FROM receipt_date)
    ORDER BY year
""")

for year, count, total in cur.fetchall():
    year_int = int(year) if year else None
    if year_int == 2025:
        status = "❌ BOGUS (QuickBooks)"
    elif year_int in (2011, 2012, 2019):
        status = "✓ Valid"
    else:
        status = "⚠️  Check"
    
    print(f"{year_int}: {count:2} invoices = ${total or 0:>10,.2f} {status}")

# Find 2025 records
print(f"\n{'='*70}")
print("2025 RECORDS (BOGUS DATA TO DELETE)")
print("="*70)

cur.execute("""
    SELECT receipt_id, receipt_date, gross_amount, source_reference, description
    FROM receipts
    WHERE vendor_name = 'WCB' 
      AND EXTRACT(YEAR FROM receipt_date) = 2025
    ORDER BY receipt_id
""")

bogus_ids = []
for row in cur.fetchall():
    receipt_id, date, amount, ref, desc = row
    desc_short = (desc[:40] + "...") if desc and len(desc) > 40 else (desc or "")
    print(f"  {receipt_id:6} | {date} | ${amount:>10,.2f} | {ref or 'N/A'} | {desc_short}")
    bogus_ids.append(receipt_id)

if bogus_ids:
    print(f"\nFound {len(bogus_ids)} bogus 2025 records to delete")
    print(f"IDs: {bogus_ids}")
    
    confirm = input("\nDelete these records? (yes/no): ")
    if confirm.lower() == 'yes':
        cur.execute("""
            DELETE FROM receipts
            WHERE receipt_id = ANY(%s)
        """, (bogus_ids,))
        conn.commit()
        print(f"✅ Deleted {cur.rowcount} records")
    else:
        print("❌ Cancelled - no changes made")
else:
    print("\n✅ No 2025 bogus data found")

conn.close()
