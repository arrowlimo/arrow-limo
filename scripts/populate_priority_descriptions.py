#!/usr/bin/env python3
"""
Populate descriptions for priority beverages based on industry standard tasting notes
This provides dispatcher guidance for most-ordered items
"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Knowledge base of descriptions for major brands
descriptions_db = {
    # Vodka
    "Absolut": "Premium Swedish vodka. Triple-distilled for smoothness. Clean finish, versatile for any mixed drink.",
    "Belvedere": "Ultra-premium Polish vodka from rye. Smooth and silky with subtle grain character.",
    "Grey Goose": "French vodka distilled from Picardy wheat. Smooth, crisp, iconic.",
    "Ketel One": "Dutch vodka with traditional copper pot still distillation. Light and clean.",
    
    # Rum
    "Bacardi": "White rum, light and crisp. Perfect base for mojitos and daiquiris.",
    "Captain Morgan": "Dark spiced rum with vanilla and cinnamon notes. Great for rum-cola.",
    "Havana Club": "Cuban rum with complex caramel notes. Smooth aging process.",
    "Mount Gay": "Premium rum from Barbados. Full-bodied with vanilla and oak.",
    "Appleton Estate": "Jamaican rum with fruity, complex profile. Excellent aged expression.",
    
    # Whiskey
    "Jack Daniel's": "Tennessee whiskey with charcoal mellowing. Smooth, approachable.",
    "Jameson": "Irish whiskey with triple distillation. Smooth, sweet, triple pot still character.",
    "Crown Royal": "Canadian blended whiskey. Smooth, balanced, perfect for any occasion.",
    "Bulleit": "Kentucky straight bourbon. High rye content gives spicy finish.",
    "Angel's Envy": "Bourbon finished in port barrels. Rich, smooth, creamy vanilla notes.",
    "Woodford Reserve": "Premium Kentucky bourbon. Complex spice and fruit notes.",
    
    # Gin
    "Tanqueray": "Classic London dry gin. Strong juniper, balanced botanicals.",
    "Beefeater": "London dry gin with prominent juniper and orange peel.",
    "Hendrick's": "Scottish gin infused with cucumber. Unique, refreshing, smooth.",
    "Bombay Sapphire": "Gin distilled with 10 botanicals. Crisp, balanced profile.",
    
    # Tequila
    "Jose Cuervo": "Classic tequila. Smooth, versatile for margaritas.",
    "Patrón": "Premium silver tequila. Smooth, crisp, clean finish.",
    "1800": "Aged tequila with smooth, refined character.",
    
    # Wine - Red
    "Apothic": "California red blend. Smooth, fruit-forward with berry notes.",
    "Barefoot Cabernet": "Full-bodied Cabernet. Rich plum and dark cherry, silky tannins.",
    "Yellow Tail Shiraz": "Australian red with bold fruit, peppery spice.",
    "Columbia Crest": "Bordeaux-style blend. Balanced, fruit-forward.",
    
    # Wine - White
    "Barefoot Pinot Grigio": "Crisp white wine. Green apple and citrus notes, light and refreshing.",
    "Barefoot Chardonnay": "California Chardonnay. Butter and vanilla, medium body.",
    "Kendall Jackson": "Riesling-style white. Aromatic, semi-dry, food-friendly.",
    "Barefoot Sauvignon Blanc": "Herbal, tropical fruit notes. Crisp, vibrant.",
    
    # Champagne/Sparkling
    "Barefoot Bubbly": "California sparkling wine. Bright bubbles, fruity, celebratory.",
    "Bollinger": "Prestigious Champagne. Complex, aged, elegant.",
    "Veuve Clicquot": "Classic Champagne. Rich, balanced, celebratory.",
    
    # Beer
    "Corona": "Mexican lager. Light, crisp, refreshing.",
    "Heineken": "Dutch lager. Crisp, balanced, slightly bitter.",
    "Stella Artois": "Belgian lager. Smooth, balanced, slightly fruity.",
    "Molson Canadian": "Canadian lager. Light, crisp, easy-drinking.",
    "Blue Moon": "American wheat ale. Smooth, with orange citrus notes.",
    
    # Cognac
    "Hennessy": "Premium Cognac. Rich, complex, elegant.",
    "Remy Martin": "Smooth Cognac from Champagne region. Refined, fruity notes.",
    
    # Non-Alcoholic
    "San Pellegrino": "Italian sparkling water. Crisp, elegant.",
}

print("="*100)
print(" POPULATING PRIORITY BEVERAGE DESCRIPTIONS")
print("="*100)

updated = 0
skipped = 0
not_found = 0

for brand_keyword, description in descriptions_db.items():
    cur.execute("""
        SELECT item_id, item_name 
        FROM beverage_products
        WHERE (description IS NULL OR description = '')
        AND item_name ILIKE %s
        ORDER BY item_name
    """, (f"%{brand_keyword}%",))
    
    items = cur.fetchall()
    
    if items:
        print(f"\n  {brand_keyword} ({len(items)} items):")
        
        for item_id, item_name in items:
            cur.execute(
                "UPDATE beverage_products SET description = %s WHERE item_id = %s",
                (description, item_id)
            )
            print(f"    ✅ {item_name:45} → Updated")
            updated += 1
    else:
        not_found += 1

conn.commit()

# Fill in generic descriptions for remaining items
print(f"\n\n  📝 Adding generic descriptions for remaining items...\n")

generic_descriptions = {
    "Vodka": "Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.",
    "Rum": "Quality rum. Full-bodied with smooth character. Perfect for cocktails.",
    "Whiskey": "Smooth whiskey. Well-rounded spirit with balanced flavor profile.",
    "Gin": "Quality gin with balanced botanicals. Classic for martinis and gin & tonics.",
    "Tequila": "Premium tequila. Smooth, versatile for margaritas and cocktails.",
    "Brandy": "Aged brandy. Rich, complex with oak and fruit character.",
    "Liqueurs": "Premium liqueur. Smooth, versatile for cocktails and shots.",
    "Wine - Red": "Red wine. Full-bodied with fruit-forward character.",
    "Wine - White": "White wine. Crisp, refreshing with balanced acidity.",
    "Champagne": "Champagne. Elegant, celebratory sparkling wine.",
    "Beer": "Quality beer. Crisp and refreshing.",
    "Craft Beer": "Artisan beer with distinctive character and flavor.",
    "Ciders": "Cider. Fruity, refreshing alternative to beer.",
    "Hard Seltzers": "Hard seltzer. Light, refreshing with natural flavors.",
}

for category, generic_desc in generic_descriptions.items():
    cur.execute("""
        SELECT COUNT(*) FROM beverage_products
        WHERE category = %s AND (description IS NULL OR description = '')
    """, (category,))
    
    count = cur.fetchone()[0]
    
    if count > 0:
        cur.execute("""
            UPDATE beverage_products
            SET description = %s
            WHERE category = %s AND (description IS NULL OR description = '')
        """, (generic_desc, category))
        
        print(f"  ✅ {category:25} → {count:3} items updated with generic description")
        updated += cur.rowcount

conn.commit()

# Final verification
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN description IS NOT NULL AND description != '' THEN 1 END) as with_desc,
        COUNT(CASE WHEN description IS NULL OR description = '' THEN 1 END) as without_desc
    FROM beverage_products
""")

total, with_desc, without_desc = cur.fetchone()

print(f"\n\n{'='*100}")
print(f"\n✅ DESCRIPTION POPULATION COMPLETE!\n")
print(f"   Total beverages:           {total}")
print(f"   With descriptions:         {with_desc} ({with_desc/total*100:.1f}%)")
print(f"   Still missing descriptions: {without_desc} ({without_desc/total*100:.1f}%)")
print(f"\n   Items updated this session: {updated}")

cur.close()
conn.close()

print(f"\n{'='*100}")
