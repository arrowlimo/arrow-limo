#!/usr/bin/env python3
import psycopg2

sql = """
SELECT receipt_id, receipt_date, vendor_name, gross_amount, description,
       source_reference, source_file, source_system, comment
FROM receipts
WHERE vendor_name = 'LEASE FINANCE'
  AND (
    COALESCE(description, '') ILIKE '%ASI%'
    OR COALESCE(source_reference, '') ILIKE '%ASI%'
    OR COALESCE(source_file, '') ILIKE '%ASI%'
    OR COALESCE(source_system, '') ILIKE '%ASI%'
    OR COALESCE(comment, '') ILIKE '%ASI%'
    OR COALESCE(canonical_vendor, '') ILIKE '%ASI%'
  )
ORDER BY receipt_date
LIMIT 200;
"""

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()
cur.execute(sql)
rows = cur.fetchall()
print(f"rows: {len(rows)}")
for r in rows:
    rid, rdate, vendor, amt, desc, src_ref, src_file, src_sys, comment = r
    print(f"{rid:>8} | {rdate} | {amt:>10} | {src_ref or ''} | {desc or ''} | {src_file or ''} | {src_sys or ''} | {comment or ''}")
cur.close(); conn.close()
