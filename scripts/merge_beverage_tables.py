"""Merge beverages table into beverage_products"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

try:
    print("🔄 Merging beverage inventory...\n")
    
    # Get all beverages
    cur.execute("""
        SELECT beverage_id, beverage_name, category, brand, price, size_ml, is_alcoholic
        FROM beverages
        WHERE is_active = true
        ORDER BY category, beverage_name
    """)
    
    beverages = cur.fetchall()
    print(f"Found {len(beverages)} active beverages\n")
    
    # Clear old beverage_products (keeping Alberta liquor we added)
    cur.execute("DELETE FROM beverage_products WHERE category NOT IN ('Whiskey', 'Vodka', 'Rum', 'Gin', 'Beer', 'Wine')")
    
    # Insert from beverages table
    added = 0
    for bev_id, name, category, brand, price, size_ml, is_alcoholic in beverages:
        try:
            cur.execute("""
                INSERT INTO beverage_products (item_name, category, unit_price, stock_quantity)
                VALUES (%s, %s, %s, 50)
            """, (
                f"{brand} {name}" if brand else name,
                category or "Beverages",
                float(price) if price else 0.00
            ))
            added += 1
            print(f"  ✅ {brand} {name:35} ${price:7.2f} ({category})")
        except Exception as e:
            print(f"  ❌ {name}: {e}")
    
    conn.commit()
    
    # Show final count
    cur.execute("SELECT COUNT(*) FROM beverage_products")
    final_count = cur.fetchone()[0]
    
    print(f"\n✅ Merged {added} beverages")
    print(f"📦 Total in beverage_products: {final_count} items")
    
except Exception as e:
    print(f"❌ Error: {e}")
    conn.rollback()
finally:
    cur.close()
    conn.close()
