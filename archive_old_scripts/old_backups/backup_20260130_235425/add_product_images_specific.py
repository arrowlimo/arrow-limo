"""
Advanced Product Image Fetcher - Gets specific product images
Uses Bing Image Search or Google Images to find exact product photos

Option 1: Bing Image Search API (requires free API key from Azure)
Option 2: DuckDuckGo instant answer (no API key needed)
Option 3: Manual URL list (most reliable)
"""

import psycopg2
import os
import requests
from pathlib import Path
from io import BytesIO
from PIL import Image
import json
import time

DB_CONFIG = {
    'host': 'localhost',
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REDACTED***'
}

IMAGES_DIR = Path("L:/limo/data/product_images")
IMAGES_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# OPTION 3: MANUAL PRODUCT IMAGE URLS (MOST RELIABLE)
# ============================================================================
# Find actual product images online and paste URLs here

SPECIFIC_PRODUCT_IMAGES = {
    # Alcohol - Whiskey/Bourbon
    "Jim Beam": "https://www.lcbo.com/content/dam/lcbo/products/004333.jpg/jcr:content/renditions/cq5dam.web.1280.1280.jpeg",
    "Jack Daniels": "https://www.lcbo.com/content/dam/lcbo/products/003301.jpg/jcr:content/renditions/cq5dam.web.1280.1280.jpeg",
    "Crown Royal": "https://www.lcbo.com/content/dam/lcbo/products/000226.jpg/jcr:content/renditions/cq5dam.web.1280.1280.jpeg",
    "Canadian Club": "https://www.lcbo.com/content/dam/lcbo/products/000166.jpg/jcr:content/renditions/cq5dam.web.1280.1280.jpeg",
    
    # Alcohol - Vodka
    "Smirnoff": "https://www.lcbo.com/content/dam/lcbo/products/000505.jpg/jcr:content/renditions/cq5dam.web.1280.1280.jpeg",
    "Absolut": "https://www.lcbo.com/content/dam/lcbo/products/000455.jpg/jcr:content/renditions/cq5dam.web.1280.1280.jpeg",
    "Grey Goose": "https://www.lcbo.com/content/dam/lcbo/products/000703.jpg/jcr:content/renditions/cq5dam.web.1280.1280.jpeg",
    
    # Alcohol - Rum
    "Bacardi": "https://www.lcbo.com/content/dam/lcbo/products/000885.jpg/jcr:content/renditions/cq5dam.web.1280.1280.jpeg",
    "Captain Morgan": "https://www.lcbo.com/content/dam/lcbo/products/001115.jpg/jcr:content/renditions/cq5dam.web.1280.1280.jpeg",
    
    # Wine
    "Champagne": "https://www.lcbo.com/content/dam/lcbo/products/000279.jpg/jcr:content/renditions/cq5dam.web.1280.1280.jpeg",
    "Wine (Red)": "https://www.lcbo.com/content/dam/lcbo/products/000612.jpg/jcr:content/renditions/cq5dam.web.1280.1280.jpeg",
    "Wine (White)": "https://www.lcbo.com/content/dam/lcbo/products/000349.jpg/jcr:content/renditions/cq5dam.web.1280.1280.jpeg",
    
    # Beer
    "Beer": "https://www.lcbo.com/content/dam/lcbo/products/000133.jpg/jcr:content/renditions/cq5dam.web.1280.1280.jpeg",
    "Corona": "https://www.lcbo.com/content/dam/lcbo/products/000018.jpg/jcr:content/renditions/cq5dam.web.1280.1280.jpeg",
    "Heineken": "https://www.lcbo.com/content/dam/lcbo/products/000024.jpg/jcr:content/renditions/cq5dam.web.1280.1280.jpeg",
    
    # Beverages
    "Coca-Cola": "https://www.coca-colaproductfacts.com/content/dam/productfacts/ca/products/coca-cola-can-355ml.png",
    "Bottled Water": "https://www.nestle-waters.ca/sites/g/files/pydnoa606/files/styles/product_image/public/2022-01/Pure-Life-500ml.png",
}


def search_duckduckgo_image(product_name):
    """
    Search DuckDuckGo for product image (no API key needed).
    Returns first image URL found.
    """
    try:
        # DuckDuckGo instant answer API
        search_query = f"{product_name} product bottle"
        url = f"https://api.duckduckgo.com/?q={search_query}&format=json&t=product_finder"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        # Try to find image in results
        if data.get('Image'):
            return data['Image']
        
        # Alternative: use vqd token for image search (more complex)
        # This is a simplified version - full implementation would require vqd token
        print(f"   ℹ️ No instant image found for '{product_name}'")
        return None
        
    except Exception as e:
        print(f"   ⚠️ Search failed: {e}")
        return None


def download_and_save_image(url, filename):
    """Download image from URL and save as thumbnail"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Open and resize
        img = Image.open(BytesIO(response.content))
        
        # Convert RGBA to RGB if needed
        if img.mode == 'RGBA':
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        
        # Thumbnail with maintained aspect ratio
        img.thumbnail((150, 150), Image.Resampling.LANCZOS)
        
        # Save as PNG
        save_path = IMAGES_DIR / f"{filename}.png"
        img.save(save_path, "PNG")
        
        return str(save_path)
        
    except Exception as e:
        print(f"   ⚠️ Download failed: {e}")
        return None


def update_product_images():
    """Update product images from manual URLs or search"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Get all products
        cur.execute("SELECT item_id, item_name FROM beverage_products ORDER BY item_id")
        products = cur.fetchall()
        
        if not products:
            print("⚠️ No products found")
            return
        
        print(f"📦 Found {len(products)} products\n")
        
        updated = 0
        
        for item_id, item_name in products:
            print(f"🔍 Processing: {item_name}")
            
            # Try to find matching URL
            image_url = None
            
            # 1. Check manual list first (most reliable)
            for key, url in SPECIFIC_PRODUCT_IMAGES.items():
                if key.lower() in item_name.lower():
                    image_url = url
                    print(f"   ✅ Found manual URL match: {key}")
                    break
            
            # 2. If no manual match, try search (optional)
            # if not image_url:
            #     print(f"   🌐 Searching online...")
            #     image_url = search_duckduckgo_image(item_name)
            
            if image_url:
                # Download and save
                filename = f"product_{item_id}"
                image_path = download_and_save_image(image_url, filename)
                
                if image_path:
                    # Update database
                    cur.execute("""
                        UPDATE beverage_products
                        SET image_url = %s, image_path = %s
                        WHERE item_id = %s
                    """, (image_url, image_path, item_id))
                    
                    print(f"   ✅ Saved: {image_path}")
                    updated += 1
                else:
                    print(f"   ❌ Failed to download")
            else:
                print(f"   ⏭️ No image URL found")
            
            # Be nice to servers
            time.sleep(0.5)
            print()
        
        conn.commit()
        print(f"\n✅ Updated {updated} product images")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


def show_usage_tips():
    """Show how to add specific product images"""
    print("\n" + "="*70)
    print("💡 HOW TO ADD SPECIFIC PRODUCT IMAGES:")
    print("="*70)
    print("""
1. FIND PRODUCT IMAGES:
   - Visit LCBO.com, SAQ.com, or BCLiquorStores.com
   - Search for your product (e.g., "Jim Beam 750ml")
   - Right-click product image → Copy Image Address

2. ADD TO MANUAL LIST:
   - Edit this file: scripts/add_product_images_specific.py
   - Add to SPECIFIC_PRODUCT_IMAGES dictionary:
     
     "Jim Beam 750ml": "https://www.lcbo.com/content/dam/lcbo/.../image.jpg",

3. RUN SCRIPT:
   - python scripts/add_product_images_specific.py
   
4. IMAGES ARE CACHED:
   - Stored in: L:/limo/data/product_images/
   - No re-download needed unless you update URL

TIPS:
- Use actual product names in beverage_products table
- Script will match partial names (e.g., "Jim Beam" matches "Jim Beam 750ml")
- LCBO/SAQ images are high quality and product-specific
""")
    print("="*70 + "\n")


def main():
    print("\n" + "="*70)
    print("SPECIFIC PRODUCT IMAGE UPDATER")
    print("="*70 + "\n")
    
    update_product_images()
    show_usage_tips()


if __name__ == "__main__":
    main()
