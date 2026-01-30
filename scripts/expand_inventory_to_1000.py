"""
Expand to 1000+ items - add more brands and regional products
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

ADDITIONAL_PRODUCTS = {
    'Whiskey': [
        'Bushmills', 'Glenmorangie', 'Glenlivet', 'Balvenie', 'Lagavulin',
        'Talisker', 'Highland Park', 'Oban', 'Glenfarclas', 'Macallan Single Malt',
        'Bowmore', 'Laphroaig', 'Ardbeg', 'Springbank', 'Dalmore'
    ],
    'Vodka': [
        'Premium Vodka Selection', 'Crystal Head', 'Chopin', 'Zubrowka', 'Russian Standard',
        'Eristoff', 'Popov', 'Barton', 'Burnetts', 'Gilbeys'
    ],
    'Rum': [
        'Diplomatico', 'Ron Zacapa', 'El Dorado', 'Brugal', 'Matusalem',
        'Zacapa 23yr', 'Havana 7yr', 'Banks Rum', 'Bundaberg', 'Pampero'
    ],
    'Gin': [
        'Plymouth Gin', 'Bols Genever', 'New Amsterdam', 'Beefeater 24', 'Monkey 47',
        'Tanqueray 10', 'Citadelle', 'Roku', 'Bombay', 'Seagram\'s Extra Dry'
    ],
    'Tequila': [
        'Hermanos Serrano', 'Casa Numero Uno', 'Benromach', 'Milagro', 'Fortaleza',
        'El Tesoro Paradiso', 'Centinela', 'Sauza Tres Mujeres', 'Siesta', 'Tecate'
    ],
    'Liqueurs': [
        'Kahlúa', 'Baileys Irish Cream', 'Cointreau', 'Grand Marnier', 'Amaretto',
        'Frangelico', 'Benedictine', 'Chartreuse', 'Drambuie', 'Chambord',
        'Midori', 'Limoncello', 'Disaronno', 'Jägermeister', 'Ouzo',
        'Campari', 'Pernod', 'Absinthe', 'Sambuca', 'Coffee Liqueur'
    ],
    'Brandy': [
        'Cognac VS', 'Cognac VSOP', 'Hennessy', 'Remy Martin', 'Courvoisier',
        'Martell', 'Pisco', 'Applejack', 'Calvados', 'Grappa'
    ],
    'Non-Alcoholic Spirits': [
        'Seedlip Grove 42', 'Seedlip Spice 94', 'Lyre\'s Dry London Spirit', 'Tansie', 'Three Spirit Ethica'
    ],
    'Hard Seltzers': [
        'White Claw Mango', 'White Claw Lime', 'Truly Variety Pack', 'Bud Light Seltzer', 'Corona Hard Seltzer',
        'Twisted Tea', 'Smirnoff Ice', 'Mike\'s Hard Lemonade', 'Burnett\'s Seltzer', 'Henry\'s Hard Soda'
    ],
    'Craft Beer': [
        'Moose Jaw Brewing', 'Big Rock Brewery', 'Noodly Appendage Ale', 'Trolley 5', 'Shed & Breakfast IPA',
        'Strathcona Brewing', 'Tool Shed Brewing', 'Folding Mountain Brewing', 'Parallel 49', 'Dead Frog Brewing'
    ],
    'Ciders': [
        'Strongbow', 'Woodchuck', 'Angry Orchard', 'Magners', 'Bulmers',
        'Ciderboys', 'Stella Artois Cidre', 'Blake\'s Hard Cider', 'Ace', 'Hornsby\'s'
    ],
}

BOTTLE_SIZES = {
    '50ml': 0.10,
    '375ml': 0.55,
    '750ml': 1.00,
    '1L': 1.25,
    '1.75L': 2.00,
}

BASE_PRICES = {
    'Whiskey': 38.00,
    'Vodka': 32.00,
    'Rum': 32.00,
    'Gin': 36.00,
    'Tequila': 38.00,
    'Liqueurs': 35.00,
    'Brandy': 45.00,
    'Non-Alcoholic Spirits': 40.00,
    'Hard Seltzers': 12.00,
    'Craft Beer': 8.50,
    'Ciders': 7.50,
}

try:
    print("\n🍾 EXPANDING INVENTORY TO 1000+ ITEMS\n")
    print("="*70)
    
    total_added = 0
    
    for category, brands in ADDITIONAL_PRODUCTS.items():
        base_price = BASE_PRICES.get(category, 30.00)
        
        # Special handling for different categories
        if category in ('Hard Seltzers', 'Ciders'):
            sizes = ['355ml', '473ml', '24-pack']
        elif category in ('Craft Beer',):
            sizes = ['473ml', '24-pack', '6-pack']
        elif category == 'Non-Alcoholic Spirits':
            sizes = ['500ml', '700ml']
        else:
            sizes = list(BOTTLE_SIZES.keys())
        
        for brand in brands:
            for size in sizes:
                try:
                    if size in BOTTLE_SIZES:
                        price = base_price * BOTTLE_SIZES[size]
                    elif size == '355ml':
                        price = base_price / 2
                    elif size == '473ml':
                        price = base_price * 0.65
                    elif size == '500ml':
                        price = base_price * 0.7
                    elif size == '700ml':
                        price = base_price * 0.95
                    elif size in ('6-pack', '24-pack'):
                        price = base_price * 6 if size == '6-pack' else base_price * 24
                    else:
                        price = base_price
                    
                    item_name = f"{brand} {size}"
                    
                    cur.execute("""
                        INSERT INTO beverage_products 
                        (item_name, category, unit_price, stock_quantity)
                        VALUES (%s, %s, %s, 50)
                    """, (item_name, category, round(float(price), 2)))
                    
                    total_added += 1
                    
                except Exception as e:
                    pass
        
        conn.commit()
    
    # Get final count
    cur.execute("SELECT COUNT(*) FROM beverage_products")
    final_count = cur.fetchone()[0]
    
    print(f"✅ Added {total_added} new items")
    print(f"📦 Total Inventory: {final_count} items")
    
    cur.execute("""
        SELECT category, COUNT(*) as cnt
        FROM beverage_products
        GROUP BY category
        ORDER BY cnt DESC
    """)
    
    print(f"\n📊 TOP CATEGORIES:\n")
    for cat, cnt in cur.fetchall()[:15]:
        print(f"  {cat:30} {cnt:4d} items")
    
    print(f"\n" + "="*70 + "\n")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    conn.rollback()
finally:
    cur.close()
    conn.close()
