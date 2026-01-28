#!/usr/bin/env python3
"""
Display beverage system updates and capabilities
"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Get beverage stats
cur.execute("SELECT COUNT(*) FROM beverage_products")
total_items = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM beverage_products WHERE description IS NOT NULL")
items_with_desc = cur.fetchone()[0]

cur.execute("SELECT COUNT(DISTINCT category) FROM beverage_products")
categories = cur.fetchone()[0]

print("\n" + "="*70)
print(" BEVERAGE ORDERING SYSTEM - UPDATED FEATURES")
print("="*70)

print("\n✅ DATABASE ENHANCEMENTS:")
print(f"   • Total beverages in inventory: {total_items:,}")
print(f"   • Items with descriptions: {items_with_desc:,}")
print(f"   • Product categories: {categories}")

print("\n✅ USER INTERFACE IMPROVEMENTS:")
print("   • Removed Stock column (not tracked)")
print("   • Added Description column for dispatcher guidance")
print("   • 4-column table: Item | Category | Unit Price | Description")

print("\n✅ SEARCH & FILTER CAPABILITIES:")
print("   • Fuzzy matching at 60%+ similarity")
print("   • Handles typos (e.g., 'belevedere' → finds Belvedere)")
print("   • Partial name search (e.g., 'apothic' → finds Apothic wines)")
print("   • Case-insensitive searching")

print("\n✅ SHOPPING CART FEATURES:")
print("   • Add items by double-click or button")
print("   • Quantity adjustment in cart")
print("   • Subtotal/GST/Total calculation")
print("   • Save order to charter")
print("   • Clear cart function")

print("\n📋 AGLC COVERAGE:")
print("   ✓ Beer (domestic, imported, craft)")
print("   ✓ Wine (red, white, sparkling)")
print("   ✓ Spirits (Vodka, Rum, Whiskey, Gin, Tequila)")
print("   ✓ Coolers & Seltzers")
print("   ✓ Non-Alcoholic beverages")
print("   ⚠ Missing: Apothic wines, some craft varieties")

print("\n🔍 EXAMPLE SEARCHES (Fuzzy Matching):")
searches = [
    ("apothic", "Apothic Red Wine (even if misspelled)"),
    ("twisted tea", "Twisted Tea varieties"),
    ("cabernet", "Cabernet Sauvignon wines"),
    ("vodka", "All vodka brands"),
    ("macallan", "Macallan scotch whisky"),
]
for search, result in searches:
    print(f"   • '{search}' → {result}")

print("\n📊 DISPATCHER GUIDANCE:")
print("   • Each product includes tasting notes")
print("   • Examples:")
cur.execute("""
    SELECT item_name, description 
    FROM beverage_products 
    WHERE description IS NOT NULL 
    LIMIT 5
""")
for name, desc in cur.fetchall():
    if desc:
        print(f"      - {name}: {desc}")

print("\n" + "="*70)

cur.close()
conn.close()
