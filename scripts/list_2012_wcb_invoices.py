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

print("All 2012 WCB Invoices (by source_reference):\n")
cur.execute("""
    SELECT source_reference, COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE vendor_name = 'WCB' AND fiscal_year = 2012 AND gross_amount > 0
    GROUP BY source_reference
    ORDER BY MIN(invoice_date)
""")

count = 0
for ref, cnt, total in cur.fetchall():
    count += 1
    ref_display = ref if ref else "N/A"
    print(f"{count:2}. Ref {ref_display:15} | {cnt:2} line items | ${total:>10,.2f}")

print(f"\nTotal unique invoice references: {count}")

print("\n" + "="*70)
print("All 2012 WCB records (detail):\n")

cur.execute("""
    SELECT receipt_id, source_reference, invoice_date, gross_amount, sub_classification, description
    FROM receipts
    WHERE vendor_name = 'WCB' AND fiscal_year = 2012 AND gross_amount > 0
    ORDER BY invoice_date, receipt_id
""")

for r in cur.fetchall():
    subcat = r[4] or "WCB"
    desc = (r[5][:30] + "...") if r[5] and len(r[5]) > 30 else (r[5] or "")
    print(f"{r[0]:6} | {r[2]} | ${r[3]:>10,.2f} | {r[1] or 'N/A':15} | {subcat:20} | {desc}")

conn.close()
