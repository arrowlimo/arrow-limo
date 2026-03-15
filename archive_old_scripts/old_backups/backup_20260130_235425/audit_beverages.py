import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Check if beverage_products table exists
cur.execute("""
    SELECT EXISTS(
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'beverage_products'
    )
""")
exists = cur.fetchone()[0]

if exists:
    print("beverage_products table EXISTS\n")
    cur.execute("SELECT COUNT(*) FROM beverage_products")
    count = cur.fetchone()[0]
    print(f"Total items: {count}\n")
    
    cur.execute("""
        SELECT category, COUNT(*) 
        FROM beverage_products 
        GROUP BY category 
        ORDER BY category
    """)
    print("Items by category:")
    for cat, cnt in cur.fetchall():
        print(f"  {cat}: {cnt}")
    
    print("\nAll items:")
    cur.execute("""
        SELECT item_name, category, unit_price, stock_quantity 
        FROM beverage_products 
        ORDER BY category, item_name
    """)
    for name, cat, price, stock in cur.fetchall():
        print(f"  {name:30} | {cat:15} | ${price:6.2f} | Stock: {stock}")
else:
    print("❌ beverage_products table does NOT exist")
    print("\nCreating sample beverage_products table...")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS beverage_products (
            item_id SERIAL PRIMARY KEY,
            item_name VARCHAR(100),
            category VARCHAR(50),
            unit_price NUMERIC(10,2),
            stock_quantity INTEGER,
            image_path VARCHAR(255)
        )
    """)
    
    # Insert sample beverages
    beverages = [
        # Non-Alcoholic Beverages
        ('Bottled Water', 'Non-Alcoholic', 2.00, 100),
        ('Coca-Cola', 'Non-Alcoholic', 2.50, 75),
        ('Diet Coke', 'Non-Alcoholic', 2.50, 60),
        ('Sprite', 'Non-Alcoholic', 2.50, 50),
        ('Ginger Ale', 'Non-Alcoholic', 2.50, 40),
        ('Orange Juice', 'Non-Alcoholic', 3.00, 50),
        ('Apple Juice', 'Non-Alcoholic', 3.00, 50),
        ('Cranberry Juice', 'Non-Alcoholic', 3.50, 30),
        ('Iced Tea', 'Non-Alcoholic', 2.75, 45),
        ('Lemonade', 'Non-Alcoholic', 3.00, 40),
        ('Coffee', 'Non-Alcoholic', 2.00, 60),
        ('Hot Chocolate', 'Non-Alcoholic', 2.50, 40),
        
        # Beer
        ('Bud Light - Single', 'Beer', 2.00, 50),
        ('Bud Light - 6-pack', 'Beer', 8.00, 30),
        ('Corona - Single', 'Beer', 2.50, 40),
        ('Corona - 6-pack', 'Beer', 12.00, 25),
        ('Heineken - Single', 'Beer', 2.75, 35),
        ('Heineken - 6-pack', 'Beer', 14.00, 20),
        ('Molson Canadian - Single', 'Beer', 2.00, 45),
        ('Molson Canadian - 6-pack', 'Beer', 8.50, 25),
        ('Labatt Blue - Single', 'Beer', 2.00, 40),
        ('Labatt Blue - 6-pack', 'Beer', 8.00, 30),
        
        # Wine
        ('Red Wine (Glass)', 'Wine', 8.00, 20),
        ('Red Wine (Bottle)', 'Wine', 30.00, 15),
        ('White Wine (Glass)', 'Wine', 8.00, 20),
        ('White Wine (Bottle)', 'Wine', 28.00, 15),
        ('Rosé Wine (Bottle)', 'Wine', 26.00, 10),
        ('Sparkling Wine (Bottle)', 'Wine', 35.00, 12),
        
        # Liquor/Spirits
        ('Vodka (Shot)', 'Liquor', 4.00, 30),
        ('Rum (Shot)', 'Liquor', 4.00, 25),
        ('Whiskey (Shot)', 'Liquor', 5.00, 20),
        ('Gin (Shot)', 'Liquor', 4.00, 20),
        ('Tequila (Shot)', 'Liquor', 4.00, 15),
        ('Champagne (Bottle)', 'Liquor', 50.00, 8),
        
        # Mixers
        ('Tonic Water', 'Mixers', 2.00, 40),
        ('Soda Water', 'Mixers', 1.50, 60),
        ('Cola Mixer', 'Mixers', 1.50, 50),
        ('Lime Juice', 'Mixers', 2.50, 30),
        ('Cranberry Mix', 'Mixers', 2.50, 25),
    ]
    
    for name, cat, price, stock in beverages:
        cur.execute("""
            INSERT INTO beverage_products (item_name, category, unit_price, stock_quantity)
            VALUES (%s, %s, %s, %s)
        """, (name, cat, price, stock))
    
    conn.commit()
    print(f"✅ Created beverage_products table with {len(beverages)} items")
    
    # Show summary
    cur.execute("""
        SELECT category, COUNT(*) 
        FROM beverage_products 
        GROUP BY category 
        ORDER BY category
    """)
    print("\nItems by category:")
    for cat, cnt in cur.fetchall():
        print(f"  {cat}: {cnt}")

cur.close()
conn.close()
