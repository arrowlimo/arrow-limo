"""Merge ALL beverage tables into beverage_products"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

try:
    print("\n🔄 COMPREHENSIVE BEVERAGE INVENTORY MERGE\n")
    print("="*70)
    
    # Add from beverage_menu (24 items)
    print("\n1️⃣ Adding items from beverage_menu (24 items)...")
    
    cur.execute('''
        SELECT beverage_id, name, category, brand, retail_price
        FROM beverage_menu
        WHERE is_active = true
        ORDER BY category, name
    ''')
    
    menu_items = cur.fetchall()
    added_from_menu = 0
    
    for bev_id, name, category, brand, retail_price in menu_items:
        try:
            full_name = f"{brand} {name}" if brand else name
            
            cur.execute('''
                INSERT INTO beverage_products (item_name, category, unit_price, stock_quantity)
                VALUES (%s, %s, %s, 75)
            ''', (full_name, category or "Beverages", float(retail_price) if retail_price else 0.00))
            
            added_from_menu += 1
            print(f"   ✅ {full_name:50} ${float(retail_price):.2f}")
        except Exception as e:
            if 'unique' not in str(e).lower():
                print(f"   ⚠️ {name}: {str(e)[:40]}")
    
    conn.commit()
    
    # Show final inventory
    print("\n" + "="*70)
    print("\n2️⃣ FINAL INVENTORY STATUS:\n")
    
    cur.execute('SELECT COUNT(*) FROM beverage_products')
    total_count = cur.fetchone()[0]
    
    cur.execute('SELECT COUNT(DISTINCT category) FROM beverage_products')
    category_count = cur.fetchone()[0]
    
    cur.execute('SELECT AVG(unit_price), MIN(unit_price), MAX(unit_price) FROM beverage_products')
    avg_price, min_price, max_price = cur.fetchone()
    
    print(f"📦 Total Items:        {total_count}")
    print(f"🏷️  Categories:         {category_count}")
    print(f"💰 Average Price:      ${avg_price:.2f}")
    print(f"💵 Price Range:        ${min_price:.2f} - ${max_price:.2f}")
    
    print(f"\n3️⃣ BY CATEGORY:\n")
    
    cur.execute('''
        SELECT category, COUNT(*), AVG(unit_price), MIN(unit_price), MAX(unit_price)
        FROM beverage_products
        GROUP BY category
        ORDER BY COUNT(*) DESC
    ''')
    
    for cat, cnt, avg, min_p, max_p in cur.fetchall():
        print(f"  {cat:20} {cnt:3d} items  Avg: ${avg:.2f}  (${min_p:.2f} - ${max_p:.2f})")
    
    print(f"\n" + "="*70)
    print(f"✅ Added {added_from_menu} items from beverage_menu")
    print(f"✅ Total comprehensive inventory: {total_count} items ready for charter ordering!")
    print("="*70 + "\n")
    
except Exception as e:
    print(f"❌ Error: {e}")
    conn.rollback()
finally:
    cur.close()
    conn.close()
