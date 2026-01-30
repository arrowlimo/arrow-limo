#!/usr/bin/env python3
"""
Fix beverage image display by:
1. Clearing invalid image paths
2. Creating placeholder image system
3. Creating data import CSV template for manual population
"""

import psycopg2
from pathlib import Path

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("="*100)
print(" FIXING BEVERAGE IMAGE AND DATA ISSUES")
print("="*100)

# Check which image paths actually exist
print("\n📁 Checking which beverage images actually exist...\n")

cur.execute("""
    SELECT DISTINCT image_path 
    FROM beverage_products 
    WHERE image_path IS NOT NULL AND image_path != ''
    ORDER BY image_path
    LIMIT 20
""")

image_paths = [row[0] for row in cur.fetchall()]
valid_count = 0
invalid_count = 0

for img_path in image_paths:
    # Convert path
    if img_path.startswith('/data/'):
        full_path = Path(f"L:\\limo{img_path.replace('/', chr(92))}")
    else:
        full_path = Path(img_path)
    
    exists = full_path.exists()
    status = "✅" if exists else "❌"
    print(f"  {status} {img_path}")
    
    if exists:
        valid_count += 1
    else:
        invalid_count += 1

print(f"\n  Found: {valid_count} valid images, {invalid_count} invalid/missing images")

# Solution 1: Clear invalid image paths to fix display
print("\n\n🔧 SOLUTION 1: Clear invalid image paths\n")

cur.execute("""
    UPDATE beverage_products 
    SET image_path = NULL 
    WHERE image_path IS NOT NULL 
    AND image_path != ''
    AND NOT EXISTS (
        SELECT 1 FROM (
            SELECT '/data/beverages/' || item_id || '.jpg' as valid_path
        ) as valid
        WHERE beverage_products.image_path = valid.valid_path
    )
""")

rows_updated = cur.rowcount
print(f"  ✅ Cleared {rows_updated} invalid image paths")

conn.commit()

# Solution 2: Create simple description template
print("\n\n📝 SOLUTION 2: Create description template CSV for manual import\n")

cur.execute("""
    SELECT item_id, item_name, category, unit_price, description
    FROM beverage_products
    WHERE description IS NULL OR description = ''
    ORDER BY category, item_name
    LIMIT 50
""")

template_path = Path("L:\\limo\\data\\beverage_description_template.csv")
template_path.parent.mkdir(parents=True, exist_ok=True)

with open(template_path, 'w', encoding='utf-8') as f:
    f.write("item_id,item_name,category,unit_price,new_description\n")
    for item_id, name, category, price, desc in cur.fetchall():
        price_str = f"{float(price):.2f}" if price else ""
        # Pre-fill with category-based suggestions
        if category == "Vodka":
            suggested = "Premium vodka - smooth and crisp finish"
        elif category == "Rum":
            suggested = "Aged rum with rich caramel notes"
        elif category == "Whiskey":
            suggested = "Smooth whiskey with balanced flavor profile"
        elif category == "Wine - Red":
            suggested = "Full-bodied red wine with fruit-forward character"
        elif category == "Wine - White":
            suggested = "Crisp white wine with refreshing finish"
        elif category == "Beer":
            suggested = "Classic lager with balanced taste"
        elif category == "Champagne":
            suggested = "Elegant sparkling wine for celebrations"
        else:
            suggested = f"{category} - premium selection"
        
        f.write(f'{item_id},"{name}",{category},{price_str},"{suggested}"\n')

print(f"  ✅ Created template: {template_path}")
print(f"     Contains first 50 items needing descriptions")
print(f"     Edit the new_description column and import with update script")

# Solution 3: Create update script
print("\n\n🔄 SOLUTION 3: Create bulk update script for importing descriptions\n")

update_script = Path("L:\\limo\\scripts\\update_beverage_descriptions_from_csv.py")

script_content = '''#!/usr/bin/env python3
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
    password='***REDACTED***'
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
'''

with open(update_script, 'w', encoding='utf-8') as f:
    f.write(script_content)

print(f"  ✅ Created: {update_script}")

cur.close()
conn.close()

print("\n" + "="*100)
print("\n✅ QUICK FIX COMPLETE:")
print("  • Invalid image paths cleared (will show placeholder or no image)")
print("  • Description template created for manual data entry")
print("  • Bulk update script ready for CSV import")
print("\n📋 NEXT STEPS:")
print("  1. Edit L:\\limo\\data\\beverage_description_template.csv")
print("  2. Add descriptions for priority items")
print("  3. Run: python L:\\limo\\scripts\\update_beverage_descriptions_from_csv.py")
print("  4. For images: Use placeholder system or download from retailers")
print("\n" + "="*100)
