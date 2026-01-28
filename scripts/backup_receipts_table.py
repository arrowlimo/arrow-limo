#!/usr/bin/env python3
"""Create SQL backup using Python directly (no pg_dump needed)."""
import psycopg2
from datetime import datetime
import os

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
backup_file = f"L:\\limo\\almsdata_backup_BEFORE_RECEIPT_REBUILD_{timestamp}.sql"

print(f"Creating Python-based backup of receipts table...")
print(f"Target: {backup_file}\n")

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Get receipt count
cur.execute("SELECT COUNT(*) FROM receipts")
total = cur.fetchone()[0]
print(f"Total receipts to backup: {total:,}")

# Create backup SQL
with open(backup_file, 'w', encoding='utf-8') as f:
    f.write(f"-- Receipt backup created: {datetime.now()}\n")
    f.write(f"-- Total receipts: {total:,}\n\n")
    f.write("BEGIN;\n\n")
    
    # Export all receipts as INSERT statements
    cur.execute("SELECT * FROM receipts ORDER BY receipt_id")
    cols = [desc[0] for desc in cur.description]
    
    batch_size = 1000
    count = 0
    
    while True:
        rows = cur.fetchmany(batch_size)
        if not rows:
            break
            
        for row in rows:
            count += 1
            if count % 5000 == 0:
                print(f"  Backed up {count:,} / {total:,} receipts...")
            
            values = []
            for val in row:
                if val is None:
                    values.append('NULL')
                elif isinstance(val, str):
                    # Escape single quotes
                    escaped = val.replace("'", "''")
                    values.append(f"'{escaped}'")
                elif isinstance(val, (int, float)):
                    values.append(str(val))
                elif isinstance(val, bool):
                    values.append('true' if val else 'false')
                else:
                    values.append(f"'{str(val)}'")
            
            f.write(f"INSERT INTO receipts ({', '.join(cols)}) VALUES ({', '.join(values)});\n")
    
    f.write("\nCOMMIT;\n")

size = os.path.getsize(backup_file) / (1024*1024)
print(f"\n✅ Backup created successfully!")
print(f"   Records: {count:,}")
print(f"   Size: {size:.1f} MB")
print(f"   Location: {backup_file}")

cur.close()
conn.close()
