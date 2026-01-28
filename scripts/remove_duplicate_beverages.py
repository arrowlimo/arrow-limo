#!/usr/bin/env python3
"""Remove duplicate beverage items, keeping the first occurrence"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("="*80)
print(" REMOVING DUPLICATE BEVERAGES")
print("="*80)

# Find duplicates and keep only the first one (lowest item_id)
cur.execute("""
    SELECT item_name, COUNT(*) as count
    FROM beverage_products
    GROUP BY item_name
    HAVING COUNT(*) > 1
    ORDER BY count DESC
""")

duplicates = cur.fetchall()
total_removed = 0

print(f"\nFound {len(duplicates)} items with duplicates:\n")

for item_name, count in duplicates:
    # Find all IDs for this item and keep the lowest one
    cur.execute("""
        SELECT item_id FROM beverage_products 
        WHERE item_name = %s 
        ORDER BY item_id
    """, (item_name,))
    
    ids = [row[0] for row in cur.fetchall()]
    keep_id = ids[0]
    delete_ids = ids[1:]
    
    # Delete the duplicates
    placeholders = ','.join(['%s'] * len(delete_ids))
    cur.execute(f"""
        DELETE FROM beverage_products 
        WHERE item_id IN ({placeholders})
    """, delete_ids)
    
    removed = cur.rowcount
    total_removed += removed
    
    print(f"  • {item_name}")
    print(f"    Kept ID: {keep_id}, Deleted: {', '.join(map(str, delete_ids))}")
    print()

conn.commit()

# Verify
cur.execute("SELECT COUNT(*) FROM beverage_products")
final_count, = cur.fetchone()

print(f"\n✅ CLEANUP COMPLETE:")
print(f"   Removed: {total_removed} duplicate items")
print(f"   Final count: {final_count} beverages")

cur.close()
conn.close()

print("\n" + "="*80)
