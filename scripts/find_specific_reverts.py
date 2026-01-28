#!/usr/bin/env python3
"""
Diagnostic helper to locate receipts affected by recent consolidations
that may need to be reverted (ASI FINANCE, RED DEER SUPERV SERVICES).
"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("Searching for LEASE FINANCE rows with ASI clues...")
cur.execute(
    """
    SELECT receipt_id, receipt_date, vendor_name, description, source_reference, source_file, gross_amount
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
    """
)
rows = cur.fetchall()
print(f"Found {len(rows)} rows")
for row in rows:
    rid, rdate, vendor, desc, src_ref, src_file, amt = row
    print(f"{rid:>8} | {rdate} | {vendor:<15} | {amt:>10} | {src_ref or ''} | {desc or ''} | {src_file or ''}")

print("\nSearching for REAL CDN SUPERS SERVICES rows with 'RED DEER SUPERV' clues...")
cur.execute(
    """
    SELECT receipt_id, receipt_date, vendor_name, description, source_reference, source_file, gross_amount
    FROM receipts
    WHERE vendor_name = 'REAL CDN SUPERS SERVICES'
      AND (
        COALESCE(description, '') ILIKE '%RED DEER SUPERV%'
        OR COALESCE(source_reference, '') ILIKE '%RED DEER SUPERV%'
        OR COALESCE(source_file, '') ILIKE '%RED DEER SUPERV%'
        OR COALESCE(comment, '') ILIKE '%RED DEER SUPERV%'
        OR COALESCE(canonical_vendor, '') ILIKE '%RED DEER SUPERV%'
      )
    ORDER BY receipt_date
    """
)
rows = cur.fetchall()
print(f"Found {len(rows)} rows")
for row in rows:
    rid, rdate, vendor, desc, src_ref, src_file, amt = row
    print(f"{rid:>8} | {rdate} | {vendor:<25} | {amt:>10} | {src_ref or ''} | {desc or ''} | {src_file or ''}")

cur.close()
conn.close()
