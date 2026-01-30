#!/usr/bin/env python3
"""
Generate shopping list for Wine & Beyond, Liquor Barn, Liquor Depot
Export high-priority items needing prices/descriptions
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
print(" GENERATE SHOPPING LIST FOR MISSING BEVERAGE DATA")
print("="*100)

# Get priority items (popular spirits and wines)
priority_categories = [
    "Vodka", "Rum", "Whiskey", "Gin", "Tequila", 
    "Wine - Red", "Wine - White", "Champagne",
    "Beer", "Craft Beer"
]

print("\n\n🛍️  PRIORITY ITEMS NEEDING DESCRIPTIONS:\n")

output_lines = []
output_lines.append("STORE,CATEGORY,ITEM_NAME,SIZE,CURRENT_PRICE,STORE_PRICE,DESCRIPTION,IMAGE_URL")

for category in priority_categories:
    cur.execute(f"""
        SELECT item_id, item_name, category, unit_price, 
               (CASE WHEN description IS NULL OR description = '' THEN 'NEEDS DATA' ELSE 'OK' END) as data_status
        FROM beverage_products
        WHERE category = %s
        AND (description IS NULL OR description = '')
        ORDER BY item_name
        LIMIT 5
    """, (category,))
    
    items = cur.fetchall()
    print(f"  {category}:")
    
    for item_id, name, cat, price, status in items:
        print(f"    • {name:40} | ${price:7.2f}")
        
        # Extract size from name
        size = "Unknown"
        if "50ml" in name:
            size = "50ml"
        elif "375ml" in name:
            size = "375ml"
        elif "750ml" in name:
            size = "750ml"
        elif "1L" in name or "1000ml" in name:
            size = "1L"
        elif "1.75L" in name:
            size = "1.75L"
        elif "355ml" in name:
            size = "355ml"
        elif "473ml" in name:
            size = "473ml"
        elif "pack" in name:
            if "24" in name:
                size = "24-pack"
            elif "12" in name:
                size = "12-pack"
            elif "6" in name:
                size = "6-pack"
        
        output_lines.append(f"[Search Here],{cat},{name},{size},{price},[Find Price],,[Find Image URL]")

# Export as searchable CSV
export_path = Path("L:\\limo\\data\\retail_research_template.csv")
export_path.parent.mkdir(parents=True, exist_ok=True)

with open(export_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(output_lines))

print(f"\n\n✅ Export complete: {export_path}")
print(f"   Contains {len(output_lines)-1} priority items")

# Create retailer reference guide
print("\n\n📚 RETAILER WEBSITE REFERENCE:\n")

retailers = {
    "Wine and Beyond": {
        "url": "https://www.wineandbeyond.com",
        "search": "Search their site by brand name (e.g., 'Apothic', 'Hennessy')",
        "categories": ["Wines", "Spirits", "Beer", "Champagne"]
    },
    "Liquor Barn": {
        "url": "https://www.liquorbarn.com",
        "search": "Browse by spirit type (Vodka, Rum, Whiskey) or search",
        "categories": ["Spirits", "Wine", "Beer", "Liqueurs"]
    },
    "Liquor Depot": {
        "url": "https://www.liquordepot.ca",
        "search": "Search by brand or category",
        "categories": ["All Categories"]
    }
}

for retailer, info in retailers.items():
    print(f"  🏪 {retailer}")
    print(f"     URL: {info['url']}")
    print(f"     How to search: {info['search']}")
    print(f"     Categories: {', '.join(info['categories'])}")
    print()

# Create manual entry form
manual_form = Path("L:\\limo\\data\\manual_beverage_data_entry.txt")

form_content = """
================================================================================
                    MANUAL BEVERAGE DATA ENTRY FORM
================================================================================

INSTRUCTIONS:
1. Visit the retailer websites listed above
2. Search for each item in the PRIORITY ITEMS list
3. Fill in the following fields
4. Save and import with: python update_beverage_descriptions_from_csv.py

================================================================================
                              ENTRY TEMPLATE
================================================================================

Item: [Brand] [Size]
Store: [Wine and Beyond / Liquor Barn / Liquor Depot]
Price: $[price]
Description: [2-3 sentence product description]
Image URL: [direct link to product image, if available]

NOTE: Description should be 2-3 sentences describing:
  - What type of spirit/wine/beer it is
  - Key taste notes or characteristics
  - Best serving suggestions or use

EXAMPLES:
  Vodka: "Premium Russian vodka with smooth finish. Excellent for classic martinis or mixed drinks. Triple distilled for purity."
  
  Wine: "Full-bodied Cabernet Sauvignon from Napa Valley. Rich dark fruit with subtle oak notes. Pairs well with grilled meats."
  
  Beer: "Crisp lager with balanced hop profile. Light and refreshing with clean finish. Perfect for any occasion."

================================================================================
                            PRIORITY RESEARCH LIST
================================================================================

HIGH PRIORITY (Most frequently ordered):
  ☐ Apothic Red 750ml - Wine category
  ☐ Hennesly VS 750ml - Spirits/Cognac
  ☐ Parallel 49 Brewing - Craft Beer
  ☐ Barefoot Cabernet Sauvignon 750ml - Wine
  ☐ San Pellegrino (various) - Non-Alcoholic

MEDIUM PRIORITY (Common selections):
  ☐ All Vodka brands (esp. Absolut, Belvedere, Grey Goose)
  ☐ All Rum brands (esp. Bacardi, Captain Morgan, Havana Club)
  ☐ All Whiskey brands (esp. Jack Daniel's, Jameson, Crown Royal)
  ☐ Popular wines (Barefoot Pinot Grigio, Yellow Tail Shiraz)
  ☐ Craft beers (Stella Artois, Heineken, Corona)

LOW PRIORITY (Specialty items):
  ☐ Liqueurs and cordials
  ☐ Hard seltzers
  ☐ Ciders
  ☐ Non-alcoholic spirits

================================================================================
                           RESEARCH LOG
================================================================================

Date: __________

Item researched: ________________________
Store visited: ________________________
Price found: $___________
Description added: 
_________________________________________________________________
_________________________________________________________________

Notes:
_________________________________________________________________

Image URL (if found): 
_________________________________________________________________


================================================================================
"""

with open(manual_form, 'w', encoding='utf-8') as f:
    f.write(form_content)

print(f"\n  ✅ Created manual entry form: {manual_form}")

cur.close()
conn.close()

print("\n" + "="*100)
print("\n✅ SHOPPING LIST GENERATION COMPLETE!")
print("\n📋 FILES CREATED:")
print(f"   1. {export_path}")
print(f"      CSV format with priority items for research")
print(f"   2. {manual_form}")
print(f"      Guideline template for manual data entry")
print("\n🔍 TO GET PRICES & DESCRIPTIONS:")
print("   1. Visit Wine and Beyond, Liquor Barn, Liquor Depot websites")
print("   2. Search for each brand/item in the export list")
print("   3. Copy prices, descriptions, and image URLs")
print("   4. Update the beverage_description_template.csv")
print("   5. Run the bulk import script")
print("\n" + "="*100)
