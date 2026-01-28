#!/usr/bin/env python
"""Export remaining GL 9999 entries for manual categorization review."""

import psycopg2
import os
import json
from datetime import datetime
import csv

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Get remaining GL 9999 entries
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.vendor_name,
        r.gross_amount,
        r.category,
        r.gl_account_code,
        r.description
    FROM receipts r
    WHERE r.gl_account_code = '9999'
    ORDER BY r.vendor_name, r.receipt_date DESC
""")

rows = cur.fetchall()

# Group by vendor
vendors = {}
for row in rows:
    vendor = row[2]
    if vendor not in vendors:
        vendors[vendor] = []
    vendors[vendor].append({
        'receipt_id': row[0],
        'receipt_date': row[1].isoformat() if row[1] else None,
        'amount': float(row[3]),
        'category': row[4],
        'description': row[6]
    })

# Export to CSV and JSON
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
csv_path = f"reports/gl_9999_manual_review_{timestamp}.csv"
json_path = csv_path.replace('.csv', '.json')

os.makedirs('reports', exist_ok=True)

with open(csv_path, 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Vendor', 'Count', 'Total_Amount', 'Sample_Date', 'Sample_Amount', 'Sample_Description'])
    for vendor in sorted(vendors.keys(), key=lambda v: len(vendors[v]), reverse=True):
        entries = vendors[vendor]
        total = sum(e['amount'] for e in entries)
        sample = entries[0]
        writer.writerow([
            vendor,
            len(entries),
            f"${total:.2f}",
            sample["receipt_date"],
            f"${sample['amount']:.2f}",
            (sample.get("description") or "")[:50]
        ])

with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(vendors, f, indent=2, default=str)

print(f"✅ Remaining GL 9999 entries: {len(rows)}")
print(f"✅ Unique vendors: {len(vendors)}")
print(f"✅ CSV export: {csv_path}")
print(f"✅ JSON export: {json_path}")

cur.close()
conn.close()
