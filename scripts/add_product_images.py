"""
Add product image support to beverage_products table and fetch thumbnails.
Uses requests + PIL to download and cache product images.
"""

import psycopg2
import os
import requests
from pathlib import Path
from io import BytesIO
from PIL import Image

DB_CONFIG = {
    'host': 'localhost',
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***'
}

# Create images directory
IMAGES_DIR = Path("L:/limo/data/product_images")
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# Sample product image URLs (you can replace with better sources)
PRODUCT_IMAGES = {
    "Bottled Water": "https://images.unsplash.com/photo-1548839140-29a749e1cf4d?w=200",
    "Coca-Cola": "https://images.unsplash.com/photo-1554866585-cd94860890b7?w=200",
    "Champagne": "https://images.unsplash.com/photo-1547595628-c61a29f496f0?w=200",
    "Wine (Red)": "https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?w=200",
    "Wine (White)": "https://images.unsplash.com/photo-1547595628-c61a29f496f0?w=200",
    "Beer": "https://images.unsplash.com/photo-1608270586620-248524c67de9?w=200",
    "Juice": "https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=200",
    "Energy Drink": "https://images.unsplash.com/photo-1622543925917-763c34f6f86a?w=200",
    "Chips": "https://images.unsplash.com/photo-1566478989037-eec170784d0b?w=200",
    "Chocolate": "https://images.unsplash.com/photo-1511381939415-e44015466834?w=200",
}


def add_image_column():
    """Add image_url and image_path columns to beverage_products"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Check if columns exist
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'beverage_products' 
            AND column_name IN ('image_url', 'image_path')
        """)
        existing = {row[0] for row in cur.fetchall()}
        
        if 'image_url' not in existing:
            cur.execute("ALTER TABLE beverage_products ADD COLUMN image_url TEXT")
            print("✅ Added image_url column")
        
        if 'image_path' not in existing:
            cur.execute("ALTER TABLE beverage_products ADD COLUMN image_path TEXT")
            print("✅ Added image_path column")
        
        conn.commit()
    except Exception as e:
        print(f"❌ Error adding columns: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


def download_image(url, filename):
    """Download image from URL and save to local cache"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Open and resize image
        img = Image.open(BytesIO(response.content))
        img.thumbnail((150, 150), Image.Resampling.LANCZOS)
        
        # Save as PNG
        save_path = IMAGES_DIR / f"{filename}.png"
        img.save(save_path, "PNG")
        
        return str(save_path)
    except Exception as e:
        print(f"   ⚠️ Failed to download {filename}: {e}")
        return None


def populate_sample_images():
    """Populate sample product images"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Get current products
        cur.execute("SELECT item_id, item_name FROM beverage_products")
        products = cur.fetchall()
        
        if not products:
            print("⚠️ No products found in beverage_products table")
            return
        
        print(f"📦 Found {len(products)} products")
        
        for item_id, item_name in products:
            # Find matching image URL
            image_url = None
            for key, url in PRODUCT_IMAGES.items():
                if key.lower() in item_name.lower():
                    image_url = url
                    break
            
            if image_url:
                print(f"🌐 Downloading image for '{item_name}'...")
                
                # Download and cache
                filename = f"product_{item_id}"
                image_path = download_image(image_url, filename)
                
                if image_path:
                    cur.execute("""
                        UPDATE beverage_products 
                        SET image_url = %s, image_path = %s
                        WHERE item_id = %s
                    """, (image_url, image_path, item_id))
                    print(f"   ✅ Saved to {image_path}")
            else:
                print(f"   ⏭️ No image found for '{item_name}'")
        
        conn.commit()
        print("\n✅ Product images updated successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


def main():
    print("=" * 60)
    print("BEVERAGE PRODUCT IMAGE IMPORTER")
    print("=" * 60)
    
    print("\nStep 1: Add image columns to database...")
    add_image_column()
    
    print("\nStep 2: Download and cache product images...")
    populate_sample_images()
    
    print("\n" + "=" * 60)
    print("✅ COMPLETE! Product images are now available.")
    print(f"📁 Images saved to: {IMAGES_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
