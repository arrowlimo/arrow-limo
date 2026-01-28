"""
Generate comprehensive beverage inventory with all bottle sizes
Creates realistic product catalog: brands × sizes = 1000+ items
"""
import psycopg2
import random

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Base products with price at 750ml (we'll calculate other sizes from this)
BASE_PRODUCTS = {
    # Whiskey/Bourbon (15 brands × 5 sizes = 75 items)
    'Whiskey': [
        'Jim Beam', 'Jack Daniels', 'Crown Royal', 'Canadian Club', 'Jameson',
        'Bulleit', 'Maker\'s Mark', 'Buffalo Trace', 'Wild Turkey', 'Woodford Reserve',
        'Four Roses', 'Knob Creek', 'Elijah Craig', 'Angel\'s Envy', 'Proper Twelve'
    ],
    
    # Vodka (12 brands × 5 sizes = 60 items)
    'Vodka': [
        'Smirnoff', 'Absolut', 'Grey Goose', 'Ketel One', 'Tito\'s',
        'Ciroc', 'Finlandia', 'Skyy', 'Belvedere', 'Stolichnaya', 'Tanqueray', 'Ruskova'
    ],
    
    # Rum (10 brands × 5 sizes = 50 items)
    'Rum': [
        'Bacardi', 'Captain Morgan', 'Kraken', 'Mount Gay', 'Sailor Jerry',
        'Myers\'s', 'Appleton Estate', 'Havana Club', 'Diplo', 'Plantation'
    ],
    
    # Gin (8 brands × 5 sizes = 40 items)
    'Gin': [
        'Tanqueray', 'Bombay Sapphire', 'Hendrick\'s', 'Beefeater', 'Jägermeister',
        'Seagram\'s', 'Gordons', 'Botanist'
    ],
    
    # Tequila (8 brands × 5 sizes = 40 items)
    'Tequila': [
        'Jose Cuervo', 'Patrón', 'El Tesoro', 'Don Julio', 'Cointreau',
        'Espolòn', 'Sauza', 'Tres Generaciones'
    ],
    
    # Wine - Red (15 labels × 3 sizes = 45 items)
    'Wine - Red': [
        'Robert Mondavi Cabernet', 'Yellow Tail Cabernet', 'Barefoot Cabernet', 'Gallo Cabernet', 'Woodbridge',
        'Santa Margherita Barbera', 'Yellowstone Merlot', 'Black Box Red', 'Barefoot Merlot', 'Barefoot Pinot Noir',
        'La Crema Pinot Noir', 'A to Z Pinot Noir', 'Columbia Crest Merlot', 'Vella Italian Red', 'Sutter Home'
    ],
    
    # Wine - White (15 labels × 3 sizes = 45 items)
    'Wine - White': [
        'Kendall Jackson Chardonnay', 'Barefoot Chardonnay', 'Yellowstone Chardonnay', 'Santa Margherita', 'Chablis',
        'Barefoot Sauvignon Blanc', 'Saint Clair Sauvignon', 'Sancerre', 'Villa Maria Sauvignon', 'Fiddlehead',
        'Barefoot Pinot Grigio', 'Barefoot Riesling', 'Yellow Tail Riesling', 'Barefoot Bubbly Brut', 'Barefoot Moscato'
    ],
    
    # Champagne/Sparkling (10 × 3 sizes = 30 items)
    'Champagne': [
        'Dom Pérignon', 'Moët & Chandon', 'Veuve Clicquot', 'Louis Roederer Cristal', 'Bollinger',
        'Taittinger', 'Krug', 'Perrier-Jouët', 'Laurent Perrier', 'Barefoot Bubbly'
    ],
    
    # Beer - Premium (20 brands × 2 sizes = 40 items)
    'Beer': [
        'Budweiser', 'Bud Light', 'Coors Light', 'Miller Lite', 'Corona',
        'Heineken', 'Guinness', 'Stella Artois', 'Peroni', 'Modelo',
        'Dos Equis', 'Labatt Blue', 'Molson Canadian', 'Blue Moon', 'Sam Adams',
        'Craft IPA Mix', 'Pale Ale', 'Porter', 'Stout', 'Belgian Ale'
    ],
}

# Bottle sizes with ml and price multipliers (750ml = 1.0x price)
BOTTLE_SIZES = {
    '50ml':   {'ml': 50,    'price_mult': 0.10},   # Miniature - 10% of 750ml
    '375ml':  {'ml': 375,   'price_mult': 0.55},   # Half bottle - 55% of 750ml
    '750ml':  {'ml': 750,   'price_mult': 1.00},   # Standard
    '1L':     {'ml': 1000,  'price_mult': 1.25},   # Liter - 25% premium
    '1.75L':  {'ml': 1750,  'price_mult': 2.00},   # Mickey/Half gallon
}

# Base prices for 750ml at category average
BASE_PRICES = {
    'Whiskey': 32.00,
    'Vodka': 30.00,
    'Rum': 27.00,
    'Gin': 32.00,
    'Tequila': 35.00,
    'Wine - Red': 18.00,
    'Wine - White': 16.00,
    'Champagne': 80.00,
    'Beer': 8.00,
}

try:
    print("\n🍷 GENERATING COMPREHENSIVE BEVERAGE INVENTORY\n")
    print("="*70)
    
    # Clear existing
    cur.execute("DELETE FROM beverage_products WHERE category IN ('Whiskey', 'Vodka', 'Rum', 'Gin', 'Tequila', 'Wine - Red', 'Wine - White', 'Champagne', 'Beer')")
    conn.commit()
    
    total_inserted = 0
    
    for category, brands in BASE_PRODUCTS.items():
        base_price = BASE_PRICES[category]
        
        # Wine and Champagne: only 3 sizes (no 50ml, no 1L usually)
        if category in ('Wine - Red', 'Wine - White', 'Champagne'):
            sizes_to_use = ['375ml', '750ml', '1.75L']
        # Beer: typically 6-pack and singles
        elif category == 'Beer':
            sizes_to_use = ['355ml (single)', '24-pack']
        # Spirits: all 5 sizes
        else:
            sizes_to_use = list(BOTTLE_SIZES.keys())
        
        print(f"\n{category}:")
        
        for brand in brands:
            for size_name in sizes_to_use:
                try:
                    if size_name in BOTTLE_SIZES:
                        size_info = BOTTLE_SIZES[size_name]
                        price = base_price * size_info['price_mult']
                    elif size_name == '355ml (single)':
                        price = 2.50
                    elif size_name == '24-pack':
                        price = 32.00
                    else:
                        price = base_price
                    
                    # Add slight randomness to prices (±5%)
                    price = round(price * (0.95 + random.random() * 0.10), 2)
                    
                    item_name = f"{brand} {size_name}"
                    
                    cur.execute("""
                        INSERT INTO beverage_products 
                        (item_name, category, unit_price, stock_quantity)
                        VALUES (%s, %s, %s, 50)
                    """, (item_name, category, float(price)))
                    
                    total_inserted += 1
                    
                except Exception as e:
                    print(f"  ⚠️ {brand} {size_name}: {str(e)[:30]}")
        
        conn.commit()
        print(f"  ✅ Added {len(brands)} × {len(sizes_to_use)} = {len(brands) * len(sizes_to_use)} items")
    
    # Show final statistics
    cur.execute("SELECT COUNT(*) FROM beverage_products")
    final_count = cur.fetchone()[0]
    
    print(f"\n" + "="*70)
    print(f"✅ INVENTORY COMPLETE!")
    print(f"📦 Total Items: {final_count}")
    print(f"💰 Price Range: See below")
    
    cur.execute("""
        SELECT category, COUNT(*), AVG(unit_price), MIN(unit_price), MAX(unit_price)
        FROM beverage_products
        GROUP BY category
        ORDER BY COUNT(*) DESC
    """)
    
    print(f"\nBREAKDOWN BY CATEGORY:\n")
    for cat, cnt, avg, min_p, max_p in cur.fetchall():
        print(f"  {cat:20} {cnt:4d} items  Avg: ${avg:7.2f}  (${min_p:6.2f} - ${max_p:7.2f})")
    
    print(f"\n" + "="*70 + "\n")
    
except Exception as e:
    print(f"❌ Error: {e}")
    conn.rollback()
finally:
    cur.close()
    conn.close()
