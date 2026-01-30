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

# Group vendors by what will change
changes = []
for vendor, count in vendors:
    standardized = standardize_vendor_name(vendor)
    if standardized != vendor:
        changes.append((vendor, standardized, count))

cur.close()
conn.close()

# Display in batches of 25
batch_size = 25
total_batches = (len(changes) + batch_size - 1) // batch_size

print(f"Total vendors to change: {len(changes)}")
print(f"Total batches: {total_batches}")
print("="*100)

for batch_num in range(total_batches):
    start = batch_num * batch_size
    end = min(start + batch_size, len(changes))
    batch = changes[start:end]
    
    print(f"\n{'='*100}")
    print(f"BATCH {batch_num + 1} of {total_batches} (vendors {start+1}-{end} of {len(changes)})")
    print(f"{'='*100}\n")
    
    for i, (original, standardized, count) in enumerate(batch, 1):
        print(f"{start+i}. ({count} receipts)")
        print(f"   FROM: {original}")
        print(f"     TO: {standardized}")
        print()
    
    if batch_num < total_batches - 1:
        response = input("Press Enter for next batch, or type 'q' to quit: ")
        if response.lower() == 'q':
            break
