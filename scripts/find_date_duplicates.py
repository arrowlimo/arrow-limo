#!/usr/bin/env python3
"""
Find duplicate WCB invoices (same reference + amount, different dates)
"""

import psycopg2
import os
from decimal import Decimal

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

print("="*70)
print("FINDING DUPLICATE INVOICES (same ref + amount, different dates)")
print("="*70)

cur.execute("""
    SELECT source_reference, gross_amount, COUNT(*), 
           array_agg(receipt_id ORDER BY receipt_date),
           array_agg(receipt_date::text ORDER BY receipt_date)
    FROM receipts
    WHERE vendor_name = 'WCB' 
      AND fiscal_year = 2012 
      AND gross_amount > 0
      AND source_reference IS NOT NULL
    GROUP BY source_reference, gross_amount
    HAVING COUNT(*) > 1
    ORDER BY source_reference, gross_amount
""")

duplicates = cur.fetchall()

if duplicates:
    print(f"\nFound {len(duplicates)} duplicate groups:\n")
    
    all_dup_ids = []
    for ref, amount, count, ids, dates in duplicates:
        print(f"Reference {ref} | ${amount:,.2f} | {count} records:")
        for i, (rid, date) in enumerate(zip(ids, dates)):
            marker = "KEEP" if i == 0 else "DELETE"
            print(f"  {marker:6} | Receipt {rid:6} | {date}")
            if i > 0:
                all_dup_ids.append(rid)
        print()
    
    print(f"Total duplicates to delete: {len(all_dup_ids)}")
    print(f"IDs: {all_dup_ids}")
    
    confirm = input("\nDelete duplicates (keep earliest date)? (yes/no): ")
    if confirm.lower() == 'yes':
        cur.execute("""
            DELETE FROM receipts
            WHERE receipt_id = ANY(%s)
        """, (all_dup_ids,))
        conn.commit()
        print(f"\n✅ Deleted {cur.rowcount} duplicate invoices")
        
        # Show new totals
        cur.execute("""
            SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
            FROM receipts
            WHERE vendor_name = 'WCB' AND fiscal_year = 2012 AND gross_amount > 0
        """)
        count, total = cur.fetchone()
        print(f"New 2012 totals: {count} invoices = ${total:,.2f}")
    else:
        print("\n❌ Cancelled")
else:
    print("\n✅ No duplicates found (same ref + amount)")

# Also check for invoices with NULL reference that might be duplicates
print(f"\n{'='*70}")
print("CHECKING NULL REFERENCE INVOICES")
print("="*70)

cur.execute("""
    SELECT receipt_id, receipt_date, gross_amount, description
    FROM receipts
    WHERE vendor_name = 'WCB' 
      AND fiscal_year = 2012 
      AND gross_amount > 0
      AND source_reference IS NULL
    ORDER BY receipt_date
""")

null_refs = cur.fetchall()
if null_refs:
    print(f"\nFound {len(null_refs)} invoices with NULL reference:")
    for rid, date, amount, desc in null_refs:
        desc_short = (desc[:40] + "...") if desc and len(desc) > 40 else (desc or "")
        print(f"  {rid:6} | {date} | ${amount:>10,.2f} | {desc_short}")
else:
    print("\n✅ No NULL reference invoices")

conn.close()
