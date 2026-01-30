"""
Download product images for all 994 beverage items
Uses multiple sources: Unsplash API, direct product image URLs, fallback thumbnails
"""
import os
import psycopg2
import requests
from urllib.parse import quote
import json
from pathlib import Path

# Create image directory
IMAGE_DIR = r"L:\limo\data\product_images"
os.makedirs(IMAGE_DIR, exist_ok=True)

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Map specific products to reliable image URLs or search terms
PRODUCT_IMAGE_SOURCES = {
    # Whiskey
    'Jim Beam': 'jim-beam-bourbon-whiskey',
    'Jack Daniels': 'jack-daniels-whiskey',
    'Crown Royal': 'crown-royal-whiskey',
    'Canadian Club': 'canadian-club',
    'Jameson': 'jameson-irish-whiskey',
    'Maker\'s Mark': 'makers-mark',
    'Woodford Reserve': 'woodford-reserve',
    
    # Vodka
    'Smirnoff': 'smirnoff-vodka',
    'Absolut': 'absolut-vodka',
    'Grey Goose': 'grey-goose-vodka',
    'Ketel One': 'ketel-one',
    'Tito\'s': 'titos-vodka',
    
    # Rum
    'Bacardi': 'bacardi-rum',
    'Captain Morgan': 'captain-morgan-rum',
    'Kraken': 'kraken-rum',
    'Mount Gay': 'mount-gay-rum',
    
    # Gin
    'Tanqueray': 'tanqueray-gin',
    'Bombay Sapphire': 'bombay-sapphire',
    'Hendrick\'s': 'hendricks-gin',
    'Beefeater': 'beefeater-gin',
    
    # Beer
    'Budweiser': 'budweiser-beer-bottle',
    'Corona': 'corona-beer',
    'Heineken': 'heineken-beer',
    'Guinness': 'guinness-beer',
    'Stella Artois': 'stella-artois-beer',
    
    # Wine
    'Robert Mondavi': 'robert-mondavi-wine',
    'Yellow Tail': 'yellow-tail-wine',
    'Barefoot': 'barefoot-wine',
    
    # Champagne
    'Dom Pérignon': 'dom-perignon-champagne',
    'Moët & Chandon': 'moet-chandon-champagne',
    'Veuve Clicquot': 'veuve-clicquot-champagne',
}

# Unsplash API key (free tier, 50 requests/hour)
UNSPLASH_API_KEY = "YOUR_UNSPLASH_API_KEY"  # Can be obtained free from unsplash.com/api

def get_image_url_unsplash(search_term):
    """Get image URL from Unsplash for a product"""
    try:
        url = f"https://api.unsplash.com/search/photos?query={quote(search_term)}&per_page=1&client_id=gZJx0xmcZWnNtEkgvp_gPAjRvXxnKDGaFJFXBWIwNDI"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('results'):
                return data['results'][0]['urls']['regular']
    except Exception as e:
        pass
    return None

def download_image(url, filepath):
    """Download image from URL and save locally"""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
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
        # Pad to square
        new_img = Image.new('RGB', (150, 150), (255, 255, 255))
        offset = ((150 - img.width) // 2, (150 - img.height) // 2)
        new_img.paste(img, offset)
        new_img.save(filepath, 'JPEG', quality=85)
        return True
    except:
        return False

print("\n🖼️  DOWNLOADING PRODUCT IMAGES (994 items)\n")
print("="*70)

try:
    # Get all products
    cur.execute("SELECT item_id, item_name, category FROM beverage_products ORDER BY item_name")
    products = cur.fetchall()
    
    downloaded = 0
    failed = 0
    
    for item_id, item_name, category in products:
        # Generate filename
        safe_name = item_name[:50].replace(' ', '_').replace('/', '_')
        filepath = os.path.join(IMAGE_DIR, f"{item_id}_{safe_name}.jpg")
        
        # Skip if already exists
        if os.path.exists(filepath):
            continue
        
        # Try to find search term from product name
        search_term = item_name
        for known_brand, search in PRODUCT_IMAGE_SOURCES.items():
            if known_brand.lower() in item_name.lower():
                search_term = search
                break
        
        # Try to download
        image_url = get_image_url_unsplash(search_term)
        
        if image_url and download_image(image_url, filepath):
            resize_image(filepath)
            
            # Update database
            cur.execute(
                "UPDATE beverage_products SET image_path = %s WHERE item_id = %s",
                (f"/data/product_images/{os.path.basename(filepath)}", item_id)
            )
            
            downloaded += 1
            if downloaded % 50 == 0:
                print(f"  ⏳ Downloaded {downloaded} images...")
                conn.commit()
        else:
            failed += 1
    
    conn.commit()
    
    # Show statistics
    cur.execute("SELECT COUNT(*) FROM beverage_products WHERE image_path IS NOT NULL")
    with_images = cur.fetchone()[0]
    
    print(f"\n" + "="*70)
    print(f"✅ Image Download Complete!")
    print(f"📸 Downloaded: {downloaded} new images")
    print(f"📊 Total with images: {with_images} / 994 items")
    print(f"❌ Failed: {failed}")
    
    # Show top categories with images
    cur.execute("""
        SELECT category, COUNT(*) as total, 
               COUNT(CASE WHEN image_path IS NOT NULL THEN 1 END) as with_images
        FROM beverage_products
        GROUP BY category
        ORDER BY with_images DESC
        LIMIT 10
    """)
    
    print(f"\n📈 COVERAGE BY CATEGORY:\n")
    for cat, total, with_img in cur.fetchall():
        pct = int(with_img / total * 100) if total > 0 else 0
        print(f"  {cat:30} {with_img:3d}/{total:3d} items ({pct:3d}%)")
    
    print(f"\n" + "="*70 + "\n")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    conn.rollback()
finally:
    cur.close()
    conn.close()
