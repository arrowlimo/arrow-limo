#!/usr/bin/env python3
"""
Audit beverage_products table for missing prices, descriptions, and image data
Generate a report for manual population from Wine and Beyond, Liquor Barn, Liquor Depot
"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("="*100)
print(" BEVERAGE PRODUCTS AUDIT - MISSING DATA DETECTION")
print("="*100)

# Check what columns exist
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name='beverage_products'
    ORDER BY ordinal_position
""")

print("\n📋 TABLE STRUCTURE:\n")
for col, dtype in cur.fetchall():
    print(f"  • {col:30} {dtype}")

# Check image-related columns
print("\n\n📸 IMAGE DATA STATUS:\n")

cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(image_url) as has_image_url,
        COUNT(image_path) as has_image_path,
        COUNT(CASE WHEN image_url IS NOT NULL AND image_url != '' THEN 1 END) as populated_url,
        COUNT(CASE WHEN image_path IS NOT NULL AND image_path != '' THEN 1 END) as populated_path
    FROM beverage_products
""")

total, has_url, has_path, pop_url, pop_path = cur.fetchone()
print(f"  Total beverages:           {total}")
print(f"  image_url column exists:   {has_url > 0}")
print(f"  image_path column exists:  {has_path > 0}")
print(f"  image_url populated:       {pop_url} ({pop_url/total*100:.1f}%)")
print(f"  image_path populated:      {pop_path} ({pop_path/total*100:.1f}%)")

# Check for NULL/missing critical data
print("\n\n❌ MISSING CRITICAL DATA:\n")

cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN unit_price IS NULL OR unit_price = 0 THEN 1 END) as missing_price,
        COUNT(CASE WHEN description IS NULL OR description = '' THEN 1 END) as missing_description,
        COUNT(CASE WHEN stock_quantity IS NULL THEN 1 END) as missing_stock
    FROM beverage_products
""")

total, miss_price, miss_desc, miss_stock = cur.fetchone()
print(f"  Missing prices:        {miss_price} items")
print(f"  Missing descriptions:  {miss_desc} items")
print(f"  Missing stock qty:     {miss_stock} items")

# Show items with zero or very low prices (likely missing data)
print("\n\n🔍 ITEMS WITH ZERO/LOW PRICES (likely incomplete):\n")

cur.execute("""
    SELECT item_name, category, unit_price, description
    FROM beverage_products
    WHERE unit_price IS NULL OR unit_price = 0
    ORDER BY category, item_name
    LIMIT 20
""")

for item_name, category, price, desc in cur.fetchall():
    price_str = f"${price:.2f}" if price else "NULL"
    desc_str = (desc[:30] + "...") if desc else "[empty]"
    print(f"  • {item_name:40} | {category:15} | {price_str:8} | {desc_str}")

# Show items with no descriptions
print("\n\n📝 ITEMS WITH NO DESCRIPTIONS:\n")

cur.execute("""
    SELECT item_name, category, unit_price
    FROM beverage_products
    WHERE description IS NULL OR description = ''
    ORDER BY category, item_name
    LIMIT 20
""")

for item_name, category, price in cur.fetchall():
    price_str = f"${price:.2f}" if price else "N/A"
    print(f"  • {item_name:40} | {category:15} | {price_str}")

# Count by issue type
print("\n\n📊 ITEMS NEEDING UPDATES BY CATEGORY:\n")

cur.execute("""
    SELECT 
        category,
        COUNT(*) as total,
        COUNT(CASE WHEN unit_price = 0 OR unit_price IS NULL THEN 1 END) as needs_price,
        COUNT(CASE WHEN description IS NULL OR description = '' THEN 1 END) as needs_desc,
        COUNT(CASE WHEN image_path IS NULL OR image_path = '' THEN 1 END) as needs_image
    FROM beverage_products
    GROUP BY category
    ORDER BY total DESC
""")

print(f"  {'Category':20} | {'Total':6} | {'No Price':8} | {'No Desc':8} | {'No Image':8}")
print(f"  {'-'*20}-+-{'-'*6}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}")

for cat, total, needs_p, needs_d, needs_i in cur.fetchall():
    print(f"  {cat:20} | {total:6} | {needs_p:8} | {needs_d:8} | {needs_i:8}")

cur.close()
conn.close()

print("\n" + "="*100)
print("\n✅ NEXT STEPS:")
print("  1. Visit Wine and Beyond, Liquor Barn, Liquor Depot websites")
print("  2. Search for items with missing prices/descriptions")
print("  3. Use update_beverage_bulk_data.py to import corrections")
print("  4. For images: Download product images to L:\\limo\\data\\beverage_images\\")
print("     Then run populate_beverage_image_paths.py to link them")
print("\n" + "="*100)
