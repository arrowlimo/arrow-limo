#!/usr/bin/env python3
"""
Report receipts that share the same receipt_date and gross_amount (potential duplicates).
Outputs CSV: reports/duplicate_receipts_by_amount_date.csv
No data changes are made.
"""
import csv
import os
import psycopg2

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'reports', 'duplicate_receipts_by_amount_date.csv')

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

cur.execute(
    """
    SELECT receipt_id,
           receipt_date,
           gross_amount,
           vendor_name,
           description,
           source_reference,
           source_file,
           source_system,
           canonical_vendor,
           mapping_status
    FROM (
        SELECT r.*, COUNT(*) OVER (PARTITION BY receipt_date, gross_amount) AS grp_count
        FROM receipts r
    ) t
    WHERE grp_count > 1
    ORDER BY receipt_date, gross_amount, receipt_id
    """
)
rows = cur.fetchall()

os.makedirs(os.path.join(os.path.dirname(__file__), '..', 'reports'), exist_ok=True)
with open(OUTPUT_PATH, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow([
        'receipt_id', 'receipt_date', 'gross_amount', 'vendor_name',
        'description', 'source_reference', 'source_file', 'source_system',
        'canonical_vendor', 'mapping_status'
    ])
    for r in rows:
        writer.writerow(r)

cur.close(); conn.close()

unique_groups = 0
if rows:
    # Count unique (date, amount) pairs
    seen = set()
    for _, rdate, amt, *_ in rows:
        key = (rdate, float(amt) if amt is not None else None)
        if key not in seen:
            seen.add(key)
    unique_groups = len(seen)

print(f"Potential duplicate groups (date + amount): {unique_groups}")
print(f"Rows written: {len(rows)}")
print(f"Output: {OUTPUT_PATH}")
