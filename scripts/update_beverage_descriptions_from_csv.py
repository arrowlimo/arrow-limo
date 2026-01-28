#!/usr/bin/env python3
"""
Update beverage descriptions from CSV file
Usage: python update_beverage_descriptions_from_csv.py [csv_file]
"""

import sys
import csv
import psycopg2

if len(sys.argv) < 2:
    print("Usage: python update_beverage_descriptions_from_csv.py <csv_file>")
    sys.exit(1)

csv_file = sys.argv[1]

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

updated = 0
skipped = 0

with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            item_id = int(row['item_id'])
            new_desc = row.get('new_description', '').strip()
            
            if not new_desc:
                skipped += 1
                continue
            
            cur.execute(
                "UPDATE beverage_products SET description = %s WHERE item_id = %s",
                (new_desc, item_id)
            )
            updated += 1
        except Exception as e:
            print(f"Error updating item {row.get('item_id')}: {e}")
            skipped += 1

conn.commit()
cur.close()
conn.close()

print(f"✅ Updated {updated} descriptions")
print(f"⏭️  Skipped {skipped} rows")
