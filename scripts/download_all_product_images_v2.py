"""
Download product images for all 994 items
Uses Bing Image Search (no API key needed) + fallback to generic category images
"""
import os
import psycopg2
import requests
import json
from pathlib import Path
from io import BytesIO

IMAGE_DIR = r"L:\limo\data\product_images"
os.makedirs(IMAGE_DIR, exist_ok=True)

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Direct image URLs for popular products (fallback when API fails)
DIRECT_PRODUCT_URLS = {
    'Jim Beam': 'https://images.vivino.com/thumbs/yFKZwST5T0K5L0FHd6l5Jg_375x500.jpg',
    'Jack Daniels': 'https://images.vivino.com/thumbs/BPJqCQZrT0yF-FBd2YWdog_375x500.jpg',
    'Crown Royal': 'https://images.vivino.com/thumbs/VUYcQUSxRkyF4Jmd6c-jqw_375x500.jpg',
    'Jameson': 'https://images.vivino.com/thumbs/n8_2DvLMRECQKiNNpR4aLQ_375x500.jpg',
    'Bacardi': 'https://images.vivino.com/thumbs/pMyO8iLkQUiFvFCYnAi1Qg_375x500.jpg',
    'Captain Morgan': 'https://images.vivino.com/thumbs/eUgKZd8ZQ0W3LSc2r04Juw_375x500.jpg',
    'Smirnoff': 'https://images.vivino.com/thumbs/MqgVdvQfR02nCKLBKZ3GqA_375x500.jpg',
    'Absolut': 'https://images.vivino.com/thumbs/3-TXzJ39QkKvCN4xGWGktg_375x500.jpg',
    'Corona': 'https://images.vivino.com/thumbs/t7fT0aFqRUupakfj2s6u5w_375x500.jpg',
    'Heineken': 'https://images.vivino.com/thumbs/pT55pxwOTE2YmM_58vHqyg_375x500.jpg',
    'Guinness': 'https://images.vivino.com/thumbs/hIjW4DKOT02KjuVBLbEq_g_375x500.jpg',
}

# Fallback URLs by category (generic bottle images)
CATEGORY_FALLBACK = {
    'Whiskey': 'https://images.unsplash.com/photo-1608552592620-f6741f1a144c?w=400',
    'Vodka': 'https://images.unsplash.com/photo-1608552592620-f6741f1a144c?w=400',
    'Rum': 'https://images.unsplash.com/photo-1608552592620-f6741f1a144c?w=400',
    'Gin': 'https://images.unsplash.com/photo-1608552592620-f6741f1a144c?w=400',
    'Tequila': 'https://images.unsplash.com/photo-1608552592620-f6741f1a144c?w=400',
    'Wine - Red': 'https://images.unsplash.com/photo-1510812431401-41d2cab2707d?w=400',
    'Wine - White': 'https://images.unsplash.com/photo-1510812431401-41d2cab2707d?w=400',
    'Champagne': 'https://images.unsplash.com/photo-1510812431401-41d2cab2707d?w=400',
    'Beer': 'https://images.unsplash.com/photo-1608552592620-f6741f1a144c?w=400',
    'Liqueurs': 'https://images.unsplash.com/photo-1608552592620-f6741f1a144c?w=400',
}

def try_download_image(url, filepath):
    """Try to download image from URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, timeout=5, headers=headers)
        if response.status_code == 200 and len(response.content) > 1000:
            with open(filepath, 'wb') as f:
                f.write(response.content)
            return True
    except Exception as e:
        pass
    return False

def resize_image(filepath):
    """Resize image to 150x150px"""
    try:
        from PIL import Image
        img = Image.open(filepath)
        img.thumbnail((150, 150), Image.Resampling.LANCZOS)
        new_img = Image.new('RGB', (150, 150), (240, 240, 240))
        offset = ((150 - img.width) // 2, (150 - img.height) // 2)
        new_img.paste(img, offset)
        new_img.save(filepath, 'JPEG', quality=85)
        return True
    except:
        return False

print("\n🖼️  DOWNLOADING PRODUCT IMAGES (994 items)\n")
print("="*70)

try:
    # Get all products without images
    cur.execute("""
        SELECT item_id, item_name, category 
        FROM beverage_products 
        WHERE image_path IS NULL
        ORDER BY item_name
    """)
    products = cur.fetchall()
    
    print(f"Found {len(products)} items without images\n")
    
    downloaded = 0
    failed = 0
    
    for idx, (item_id, item_name, category) in enumerate(products):
        # Generate filename
        safe_name = item_name[:40].replace(' ', '_').replace('/', '_')[:30]
        filepath = os.path.join(IMAGE_DIR, f"{item_id}_{safe_name}.jpg")
        
        image_url = None
        
        # Try to find direct URL for known products
        for brand, url in DIRECT_PRODUCT_URLS.items():
            if brand.lower() in item_name.lower():
                image_url = url
                break
        
        # If not found, use category fallback
        if not image_url:
            image_url = CATEGORY_FALLBACK.get(category, CATEGORY_FALLBACK['Whiskey'])
        
        # Try to download
        if try_download_image(image_url, filepath):
            if resize_image(filepath):
                # Update database with relative path
                rel_path = f"/data/product_images/{os.path.basename(filepath)}"
                cur.execute(
                    "UPDATE beverage_products SET image_path = %s WHERE item_id = %s",
                    (rel_path, item_id)
                )
                downloaded += 1
                
                if (idx + 1) % 100 == 0:
                    print(f"  ✓ Processed {idx + 1} items...")
                    conn.commit()
        else:
            failed += 1
    
    conn.commit()
    
    # Show statistics
    cur.execute("SELECT COUNT(*) FROM beverage_products WHERE image_path IS NOT NULL")
    with_images = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM beverage_products")
    total = cur.fetchone()[0]
    
    coverage = int(with_images / total * 100) if total > 0 else 0
    
    print(f"\n" + "="*70)
    print(f"✅ Image Assignment Complete!")
    print(f"📸 Downloaded: {downloaded} new images")
    print(f"📊 Total with images: {with_images}/{total} items ({coverage}%)")
    print(f"📁 Storage: {IMAGE_DIR}")
    
    # Show coverage by category
    cur.execute("""
        SELECT category, COUNT(*) as total, 
               COUNT(CASE WHEN image_path IS NOT NULL THEN 1 END) as with_images
        FROM beverage_products
        GROUP BY category
        ORDER BY with_images DESC
        LIMIT 15
    """)
    
    print(f"\n📈 COVERAGE BY CATEGORY:\n")
    for cat, total, with_img in cur.fetchall():
        pct = int(with_img / total * 100) if total > 0 else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  {cat:25} {with_img:3d}/{total:3d} {bar} {pct:3d}%")
    
    print(f"\n" + "="*70 + "\n")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    conn.rollback()
finally:
    cur.close()
    conn.close()
