"""
Create beverage_products table and populate with sample data
"""
import psycopg2

DB_CONFIG = {
    'host': 'localhost',
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REDACTED***'
}

def create_table():
    """Create beverage_products table"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS beverage_products (
                item_id SERIAL PRIMARY KEY,
                item_name VARCHAR(255) NOT NULL,
                category VARCHAR(100),
                unit_price NUMERIC(10, 2) NOT NULL,
                stock_quantity INTEGER,
                image_url TEXT,
                image_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert sample products if table is empty
        cur.execute("SELECT COUNT(*) FROM beverage_products")
        if cur.fetchone()[0] == 0:
            cur.execute("""
                INSERT INTO beverage_products (item_name, category, unit_price, stock_quantity)
                VALUES
                    ('Bottled Water', 'Beverages', 2.00, 100),
                    ('Coca-Cola', 'Beverages', 2.50, 50),
                    ('Champagne (Bottle)', 'Alcohol', 45.00, 20),
                    ('Wine (Red)', 'Alcohol', 35.00, 15),
                    ('Wine (White)', 'Alcohol', 32.00, 15),
                    ('Beer (6-pack)', 'Alcohol', 18.00, 30),
                    ('Juice Box', 'Beverages', 1.50, 80),
                    ('Energy Drink', 'Beverages', 3.50, 40),
                    ('Chips', 'Snacks', 3.00, 60),
                    ('Chocolate Bar', 'Snacks', 2.50, 75)
            """)
            print("✅ Inserted 10 sample products")
        
        conn.commit()
        print("✅ beverage_products table created/verified")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    create_table()
