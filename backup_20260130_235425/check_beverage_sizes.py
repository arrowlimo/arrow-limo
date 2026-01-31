#!/usr/bin/env python3
"""Check beverage size coverage - should match full liquor store selection"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("="*80)
print(" BEVERAGE SIZE COVERAGE ANALYSIS")
print("="*80)

# Standard sizes
STANDARD_SPIRITS_SIZES = ["50ml", "375ml", "750ml", "1L", "1.75L"]
STANDARD_WINE_SIZES = ["375ml", "750ml", "1L", "1.75L"]
STANDARD_BEER_SIZES = ["355ml", "473ml", "6-pack", "12-pack", "24-pack"]

# Check spirits
spirits_categories = ["Vodka", "Rum", "Whiskey", "Gin", "Tequila", "Brandy", "Liqueurs"]

print("\n🥃 SPIRITS - Standard sizes should be: 50ml, 375ml, 750ml, 1L, 1.75L\n")

for category in spirits_categories:
    cur.execute("""
        SELECT item_name FROM beverage_products WHERE category = %s ORDER BY item_name
    """, (category,))
    
    items = [row[0] for row in cur.fetchall()]
    if not items:
        continue
    
    sizes = set()
    for item in items:
        # Check longer patterns first to avoid substring matches (e.g., "50ml" in "750ml")
        if "1.75L" in item or "1750ml" in item:
            sizes.add("1.75L")
        elif "1L" in item or "1000ml" in item:
            sizes.add("1L")
        elif "750ml" in item:
            sizes.add("750ml")
        elif "473ml" in item:
            sizes.add("473ml")
        elif "375ml" in item:
            sizes.add("375ml")
        elif "200ml" in item:
            sizes.add("200ml")
        elif "50ml" in item:
            sizes.add("50ml")
    
    missing = [s for s in STANDARD_SPIRITS_SIZES if s not in sizes]
    sizes_str = ", ".join(sorted(sizes)) if sizes else "NONE"
    missing_str = ", ".join(missing) if missing else "NONE"
    
    print(f"  {category:18} | Found: {sizes_str:35} | Missing: {missing_str}")

# Check wine
wine_categories = ["Wine - Red", "Wine - White", "Champagne", "Wine"]

print("\n🍷 WINE - Standard sizes should be: 375ml, 750ml, 1L, 1.75L\n")

for category in wine_categories:
    cur.execute("""
        SELECT item_name FROM beverage_products WHERE category = %s ORDER BY item_name
    """, (category,))
    
    items = [row[0] for row in cur.fetchall()]
    if not items:
        continue
    
    sizes = set()
    for item in items:
        # Check longer patterns first
        if "1.75L" in item or "1750ml" in item:
            sizes.add("1.75L")
        elif "1L" in item or "1000ml" in item:
            sizes.add("1L")
        elif "750ml" in item:
            sizes.add("750ml")
        elif "375ml" in item:
            sizes.add("375ml")
    
    missing = [s for s in STANDARD_WINE_SIZES if s not in sizes]
    sizes_str = ", ".join(sorted(sizes)) if sizes else "NONE"
    missing_str = ", ".join(missing) if missing else "NONE"
    
    print(f"  {category:18} | Found: {sizes_str:35} | Missing: {missing_str}")

# Check beer/coolers
beer_categories = ["Beer", "Craft Beer", "Ciders", "Hard Seltzers"]

print("\n🍺 BEER & COOLERS - Standard sizes should be: 355ml, 473ml, 6-pack, 12-pack, 24-pack\n")

for category in beer_categories:
    cur.execute("""
        SELECT item_name FROM beverage_products WHERE category = %s ORDER BY item_name
    """, (category,))
    
    items = [row[0] for row in cur.fetchall()]
    if not items:
        continue
    
    sizes = set()
    for item in items:
        # Check longer patterns first
        if "24-pack" in item or "24 pack" in item:
            sizes.add("24-pack")
        elif "12-pack" in item or "12 pack" in item:
            sizes.add("12-pack")
        elif "6-pack" in item or "6 pack" in item:
            sizes.add("6-pack")
        elif "473ml" in item:
            sizes.add("473ml")
        elif "355ml" in item:
            sizes.add("355ml")
    
    missing = [s for s in STANDARD_BEER_SIZES if s not in sizes]
    sizes_str = ", ".join(sorted(sizes)) if sizes else "NONE"
    missing_str = ", ".join(missing) if missing else "NONE"
    
    print(f"  {category:18} | Found: {sizes_str:35} | Missing: {missing_str}")

# Overall summary
cur.execute("SELECT COUNT(*) FROM beverage_products")
total_items = cur.fetchone()[0]

size_mapping = {
    "50ml": 0,
    "200ml": 1,
    "375ml": 2,
    "473ml": 3,
    "750ml": 4,
    "1L": 5,
    "1.75L": 6,
    "Multi-pack": 7,
}

size_counts = {}
cur.execute("SELECT item_name FROM beverage_products")
for (item,) in cur.fetchall():
    # Check longer patterns first to avoid substring matches
    if "1.75L" in item or "1750ml" in item:
        size_counts["1.75L"] = size_counts.get("1.75L", 0) + 1
    elif "1L" in item or "1000ml" in item:
        size_counts["1L"] = size_counts.get("1L", 0) + 1
    elif "750ml" in item:
        size_counts["750ml"] = size_counts.get("750ml", 0) + 1
    elif "473ml" in item:
        size_counts["473ml"] = size_counts.get("473ml", 0) + 1
    elif "375ml" in item:
        size_counts["375ml"] = size_counts.get("375ml", 0) + 1
    elif "50ml" in item:
        size_counts["50ml"] = size_counts.get("50ml", 0) + 1
    elif "24-pack" in item or "24 pack" in item:
        size_counts["Multi-pack"] = size_counts.get("Multi-pack", 0) + 1
    elif "12-pack" in item or "12 pack" in item:
        size_counts["Multi-pack"] = size_counts.get("Multi-pack", 0) + 1
    elif "6-pack" in item or "6 pack" in item:
        size_counts["Multi-pack"] = size_counts.get("Multi-pack", 0) + 1
    elif "pack" in item:
        size_counts["Multi-pack"] = size_counts.get("Multi-pack", 0) + 1

print("\n📊 OVERALL SIZE DISTRIBUTION:\n")
for size in sorted(size_counts.keys(), key=lambda x: size_mapping.get(x, 99)):
    count = size_counts[size]
    percent = (count / total_items) * 100 if total_items > 0 else 0
    bar = "█" * int(percent / 2)
    print(f"  {size:15} | {count:4} items ({percent:5.1f}%) {bar}")

untagged = total_items - sum(size_counts.values())
if untagged > 0:
    percent = (untagged / total_items) * 100
    bar = "█" * int(percent / 2)
    print(f"  {'(untagged)':15} | {untagged:4} items ({percent:5.1f}%) {bar}")

cur.close()
conn.close()

print("\n" + "="*80)
