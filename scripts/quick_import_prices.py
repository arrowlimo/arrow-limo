"""Quick import of Alberta liquor prices"""
import psycopg2

DB_CONFIG = {
    'host': 'localhost',
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***'
}

ALBERTA_LIQUOR_PRICES = {
    # Whiskey/Bourbon (750ml)
    "Jim Beam 750ml": {"price": 29.99, "category": "Whiskey", "size": "750ml"},
    "Jack Daniels 750ml": {"price": 34.99, "category": "Whiskey", "size": "750ml"},
    "Crown Royal 750ml": {"price": 32.99, "category": "Whiskey", "size": "750ml"},
    "Canadian Club 750ml": {"price": 24.99, "category": "Whiskey", "size": "750ml"},
    "Jameson Irish Whiskey 750ml": {"price": 34.99, "category": "Whiskey", "size": "750ml"},
    
    # Vodka (750ml)
    "Smirnoff Vodka 750ml": {"price": 24.99, "category": "Vodka", "size": "750ml"},
    "Absolut Vodka 750ml": {"price": 29.99, "category": "Vodka", "size": "750ml"},
    "Grey Goose Vodka 750ml": {"price": 44.99, "category": "Vodka", "size": "750ml"},
    
    # Rum (750ml)
    "Bacardi White Rum 750ml": {"price": 24.99, "category": "Rum", "size": "750ml"},
    "Captain Morgan Spiced 750ml": {"price": 26.99, "category": "Rum", "size": "750ml"},
    
    # Gin (750ml)
    "Tanqueray Gin 750ml": {"price": 32.99, "category": "Gin", "size": "750ml"},
    "Bombay Sapphire 750ml": {"price": 29.99, "category": "Gin", "size": "750ml"},
    
    # Wine (750ml)
    "Red Wine (House) 750ml": {"price": 15.99, "category": "Wine", "size": "750ml"},
    "White Wine (House) 750ml": {"price": 14.99, "category": "Wine", "size": "750ml"},
    "Champagne 750ml": {"price": 45.00, "category": "Wine", "size": "750ml"},
    
    # Beer
    "Corona 12-pack": {"price": 26.99, "category": "Beer", "size": "12x355ml"},
    "Heineken 12-pack": {"price": 27.99, "category": "Beer", "size": "12x355ml"},
    "Craft Beer 6-pack": {"price": 18.00, "category": "Beer", "size": "6x355ml"},
    
    # Non-Alcoholic
    "Coca-Cola 12-pack": {"price": 6.99, "category": "Beverages", "size": "12x355ml"},
    "Bottled Water (case)": {"price": 2.00, "category": "Beverages", "size": "24x500ml"},
    "Energy Drink 4-pack": {"price": 8.99, "category": "Beverages", "size": "4x473ml"},
}

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

try:
    # First, clear old sample data
    cur.execute("DELETE FROM beverage_products")
    print("🗑️ Cleared old sample data")
    
    # Import new products
    imported = 0
    for product_name, data in ALBERTA_LIQUOR_PRICES.items():
        cur.execute("""
            INSERT INTO beverage_products 
            (item_name, category, unit_price, stock_quantity)
            VALUES (%s, %s, %s, 100)
        """, (product_name, data['category'], data['price']))
        imported += 1
        print(f"➕ {product_name:40} ${data['price']:6.2f}")
    
    conn.commit()
    print(f"\n✅ Imported {imported} products with Alberta prices")
    
except Exception as e:
    print(f"❌ Error: {e}")
    conn.rollback()
finally:
    cur.close()
    conn.close()
