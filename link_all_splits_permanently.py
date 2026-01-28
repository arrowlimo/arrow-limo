#!/usr/bin/env python3
"""
Link ALL identified split receipts in 2012 and 2019 with split_group_id
Uses the same grouping logic as the analysis: (vendor, date) pairs
"""
import os
import psycopg2
from collections import defaultdict
import re

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

print("\n" + "=" * 100)
print("LINKING ALL SPLIT RECEIPTS PERMANENTLY (2012 & 2019)")
print("=" * 100)

# Find receipts with SPLIT pattern
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, description
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) IN (2012, 2019)
      AND description ILIKE '%SPLIT%'
    ORDER BY receipt_date, vendor_name, gross_amount DESC
""")

all_splits = cur.fetchall()
print(f"\n📊 Found {len(all_splits)} receipts with SPLIT pattern\n")

# Group by (vendor, date)
split_groups = defaultdict(list)

for receipt_id, rec_date, vendor, amount, desc in all_splits:
    split_info = {
        'receipt_id': receipt_id,
        'date': rec_date,
        'vendor': vendor,
        'amount': float(amount),
        'description': desc or ""
    }
    
    group_key = (vendor, rec_date)
    split_groups[group_key].append(split_info)

# Link all split pairs permanently
linked_count = 0
receipt_count = 0
errors = []

for (vendor, rec_date), parts in sorted(split_groups.items()):
    if len(parts) >= 2:  # Only actual splits (2+ parts)
        # Use the smallest receipt_id as the group_id (stable anchor point)
        group_id = min(p['receipt_id'] for p in parts)
        
        # Update all receipts in this group
        receipt_ids = [p['receipt_id'] for p in parts]
        total_amount = sum(p['amount'] for p in parts)
        
        placeholders = ','.join(['%s'] * len(receipt_ids))
        update_sql = f"""
            UPDATE receipts
            SET split_group_id = %s
            WHERE receipt_id IN ({placeholders})
        """
        
        try:
            cur.execute(update_sql, [group_id] + receipt_ids)
            linked_count += 1
            receipt_count += len(receipt_ids)
            
            # Verify
            cur.execute(f"""
                SELECT COUNT(*) FROM receipts 
                WHERE split_group_id = %s
            """, (group_id,))
            count = cur.fetchone()[0]
            
            if count != len(receipt_ids):
                errors.append(f"⚠️ {vendor} {rec_date}: Expected {len(receipt_ids)} linked, got {count}")
            else:
                print(f"✓ {vendor:45} {rec_date} → Linked {len(receipt_ids):2} receipts (${total_amount:.2f})")
        
        except Exception as e:
            errors.append(f"❌ {vendor} {rec_date}: {str(e)}")
            print(f"❌ {vendor:45} {rec_date} → ERROR: {str(e)}")

# Commit all changes
try:
    conn.commit()
    print(f"\n✅ Committed {linked_count} split groups ({receipt_count} total receipts)")
except Exception as e:
    conn.rollback()
    print(f"❌ Commit failed: {e}")
    errors.append(f"Commit error: {e}")

# Show verification
print("\n" + "=" * 100)
print("VERIFICATION")
print("=" * 100)

cur.execute("""
    SELECT split_group_id, COUNT(*) as count, SUM(gross_amount) as total
    FROM receipts
    WHERE split_group_id IS NOT NULL
      AND EXTRACT(YEAR FROM receipt_date) IN (2012, 2019)
    GROUP BY split_group_id
    ORDER BY count DESC
""")

split_verification = cur.fetchall()
print(f"\n✓ Split groups created: {len(split_verification)}")
print(f"✓ Total receipts linked: {sum(v[1] for v in split_verification)}")

# Show sample linked groups
print("\nSample linked groups:")
for split_id, count, total in split_verification[:5]:
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount
        FROM receipts
        WHERE split_group_id = %s
        ORDER BY gross_amount DESC
    """, (split_id,))
    
    parts = cur.fetchall()
    print(f"\n  Group ID #{split_id} ({count} parts, total ${total:.2f}):")
    for rid, vendor, amount in parts:
        print(f"    Receipt #{rid:6} | {vendor:25} | ${amount:>7.2f}")

print("\n" + "=" * 100)
print("ERROR LOG")
print("=" * 100)

if errors:
    print(f"\n⚠️ {len(errors)} issue(s) found:")
    for error in errors:
        print(error)
else:
    print("✅ No errors!")

cur.close()
conn.close()

print("\n✅ Split linking complete!")
