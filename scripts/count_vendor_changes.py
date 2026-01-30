import psycopg2
import re
import sys
sys.path.insert(0, 'l:/limo/scripts')
from apply_vendor_standardization import standardize_vendor_name

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

cur.execute("""
    SELECT vendor_name, COUNT(*) as count
    FROM receipts
    WHERE vendor_name IS NOT NULL AND vendor_name <> ''
    GROUP BY vendor_name
    ORDER BY count DESC
""")

vendors = cur.fetchall()
total_unique = len(vendors)
changed_count = 0
unchanged_count = 0
total_receipts_changed = 0

for vendor, count in vendors:
    standardized = standardize_vendor_name(vendor)
    if standardized != vendor:
        changed_count += 1
        total_receipts_changed += count

for vendor, count in vendors:
    standardized = standardize_vendor_name(vendor)
    if standardized == vendor:
        unchanged_count += 1

print(f"Total unique vendor names: {total_unique}")
print(f"Vendors that will be changed: {changed_count}")
print(f"Vendors that will stay the same: {unchanged_count}")
print(f"Total receipts affected: {total_receipts_changed:,} out of 22,549")
print(f"Percentage of vendors changed: {(changed_count/total_unique)*100:.1f}%")

cur.close()
conn.close()
