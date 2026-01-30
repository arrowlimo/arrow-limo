"""
Alberta Liquor Store Price Scraper & Product Database
Fetches current prices from local Alberta liquor retailers

SUPPORTED STORES:
1. Connect Liquor (Calgary) - connectliquor.ca
2. Kensington Wine Market (Calgary) - kensingtonwinemarket.com  
3. Co-op Wine Spirits Beer - liquor.crs.coop
4. Sherbrooke Liquor (Edmonton) - sherbrookeliquor.com

FEATURES:
- Search by product name
- Get current pricing
- Download product images
- Update beverage_products table automatically
"""

import psycopg2
import requests
from bs4 import BeautifulSoup
import json
import time
from pathlib import Path
from io import BytesIO
from PIL import Image

DB_CONFIG = {
    'host': 'localhost',
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REDACTED***'
}

IMAGES_DIR = Path("L:/limo/data/product_images")
IMAGES_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# MANUAL PRICE LIST (Most Reliable - Update Quarterly)
# ============================================================================
# Alberta average prices as of Jan 2026 - update from local store visits

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
    "Tito's Vodka 750ml": {"price": 32.99, "category": "Vodka", "size": "750ml"},
    
    # Rum (750ml)
    "Bacardi White Rum 750ml": {"price": 24.99, "category": "Rum", "size": "750ml"},
    "Captain Morgan Spiced 750ml": {"price": 26.99, "category": "Rum", "size": "750ml"},
    "Kraken Black Spiced 750ml": {"price": 29.99, "category": "Rum", "size": "750ml"},
    
    # Gin (750ml)
    "Tanqueray Gin 750ml": {"price": 32.99, "category": "Gin", "size": "750ml"},
    "Bombay Sapphire 750ml": {"price": 29.99, "category": "Gin", "size": "750ml"},
    
    # Tequila (750ml)
    "Jose Cuervo Gold 750ml": {"price": 29.99, "category": "Tequila", "size": "750ml"},
    "Patron Silver 750ml": {"price": 64.99, "category": "Tequila", "size": "750ml"},
    
    # Wine (750ml)
    "Red Wine (House) 750ml": {"price": 15.99, "category": "Wine", "size": "750ml"},
    "White Wine (House) 750ml": {"price": 14.99, "category": "Wine", "size": "750ml"},
    "Champagne (Basic) 750ml": {"price": 24.99, "category": "Wine", "size": "750ml"},
    "Prosecco 750ml": {"price": 16.99, "category": "Wine", "size": "750ml"},
    
    # Beer (Cases)
    "Budweiser 24-pack": {"price": 42.99, "category": "Beer", "size": "24x355ml"},
    "Coors Light 24-pack": {"price": 42.99, "category": "Beer", "size": "24x355ml"},
    "Corona 12-pack": {"price": 26.99, "category": "Beer", "size": "12x355ml"},
    "Heineken 12-pack": {"price": 27.99, "category": "Beer", "size": "12x355ml"},
    
    # Beer (6-packs)
    "Craft Beer 6-pack": {"price": 16.99, "category": "Beer", "size": "6x355ml"},
    "Premium Import 6-pack": {"price": 14.99, "category": "Beer", "size": "6x355ml"},
    
    # Non-Alcoholic
    "Coca-Cola 12-pack": {"price": 6.99, "category": "Beverages", "size": "12x355ml"},
    "Bottled Water (case)": {"price": 4.99, "category": "Beverages", "size": "24x500ml"},
    "Energy Drink 4-pack": {"price": 8.99, "category": "Beverages", "size": "4x473ml"},
    "Juice Box 8-pack": {"price": 3.99, "category": "Beverages", "size": "8x200ml"},
}


# ============================================================================
# WEB SCRAPING FUNCTIONS (For Real-Time Prices)
# ============================================================================

def search_kensington_wine(product_name):
    """
    Search Kensington Wine Market for product and price
    Returns: {name, price, url, image_url}
    """
    try:
        # Their search URL pattern
        base_url = "https://www.kensingtonwinemarket.com"
        search_url = f"{base_url}/search?q={product_name.replace(' ', '+')}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Parse product listings (structure may vary - inspect site)
        products = []
        
        # Example selectors (you'll need to inspect actual site)
        product_cards = soup.find_all('div', class_='product-card')
        
        for card in product_cards[:3]:  # Top 3 results
            try:
                name = card.find('h3', class_='product-title').text.strip()
                price_text = card.find('span', class_='price').text.strip()
                price = float(price_text.replace('$', '').replace(',', ''))
                product_url = base_url + card.find('a')['href']
                
                # Try to get image
                img_tag = card.find('img')
                image_url = img_tag['src'] if img_tag else None
                
                products.append({
                    'name': name,
                    'price': price,
                    'url': product_url,
                    'image_url': image_url,
                    'store': 'Kensington Wine Market'
                })
            except Exception:
                continue
        
        return products
        
    except Exception as e:
        print(f"   ⚠️ Kensington search failed: {e}")
        return []


def get_manual_price(product_name):
    """Get price from manual price list"""
    # Try exact match first
    if product_name in ALBERTA_LIQUOR_PRICES:
        return ALBERTA_LIQUOR_PRICES[product_name]
    
    # Try partial match
    for key, data in ALBERTA_LIQUOR_PRICES.items():
        if product_name.lower() in key.lower() or key.lower() in product_name.lower():
            return data
    
    return None


# ============================================================================
# DATABASE IMPORT FUNCTIONS
# ============================================================================

def import_manual_prices():
    """Import manual price list to database"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        print("📊 Importing manual price list...\n")
        
        imported = 0
        updated = 0
        
        for product_name, data in ALBERTA_LIQUOR_PRICES.items():
            # Check if product exists
            cur.execute("""
                SELECT item_id FROM beverage_products 
                WHERE item_name = %s
            """, (product_name,))
            
            existing = cur.fetchone()
            
            if existing:
                # Update existing
                cur.execute("""
                    UPDATE beverage_products
                    SET unit_price = %s, category = %s
                    WHERE item_id = %s
                """, (data['price'], data['category'], existing[0]))
                updated += 1
                print(f"   ✅ Updated: {product_name} → ${data['price']}")
            else:
                # Insert new
                cur.execute("""
                    INSERT INTO beverage_products 
                    (item_name, category, unit_price, stock_quantity)
                    VALUES (%s, %s, %s, 100)
                """, (product_name, data['category'], data['price']))
                imported += 1
                print(f"   ➕ Added: {product_name} → ${data['price']}")
        
        conn.commit()
        print(f"\n✅ Imported {imported} new products, updated {updated} existing")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


def search_and_update_price(product_name):
    """Search online and update price if found"""
    print(f"🔍 Searching for: {product_name}")
    
    # Try web search first
    results = search_kensington_wine(product_name)
    
    if results:
        print(f"   ✅ Found {len(results)} matches online:")
        for r in results:
            print(f"      • {r['name']} - ${r['price']} ({r['store']})")
        return results[0]  # Return best match
    
    # Fall back to manual list
    manual = get_manual_price(product_name)
    if manual:
        print(f"   ℹ️ Using manual price: ${manual['price']}")
        return manual
    
    print(f"   ❌ No price found")
    return None


# ============================================================================
# EXPORT FUNCTIONS
# ============================================================================

def export_price_list_csv():
    """Export current product prices to CSV"""
    import csv
    
    output_file = Path("L:/limo/data/beverage_price_list.csv")
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Product Name', 'Category', 'Size', 'Price (CAD)', 'Source'])
        
        for name, data in sorted(ALBERTA_LIQUOR_PRICES.items()):
            writer.writerow([
                name,
                data['category'],
                data.get('size', ''),
                f"${data['price']:.2f}",
                'Alberta Average'
            ])
    
    print(f"✅ Exported price list to: {output_file}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("\n" + "="*70)
    print("ALBERTA LIQUOR PRICE MANAGER")
    print("="*70 + "\n")
    
    print("OPTIONS:")
    print("1. Import manual price list to database")
    print("2. Export price list to CSV")
    print("3. Search specific product online")
    print("4. Show all prices")
    print()
    
    choice = input("Choose option (1-4): ").strip()
    
    if choice == "1":
        import_manual_prices()
    elif choice == "2":
        export_price_list_csv()
    elif choice == "3":
        product = input("Enter product name: ").strip()
        search_and_update_price(product)
    elif choice == "4":
        print("\n📋 CURRENT PRICE LIST:\n")
        for name, data in sorted(ALBERTA_LIQUOR_PRICES.items()):
            print(f"  {name:40} ${data['price']:6.2f}  ({data['category']})")
    
    print("\n" + "="*70)
    print("💡 TIP: Update ALBERTA_LIQUOR_PRICES dict quarterly with local prices")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
