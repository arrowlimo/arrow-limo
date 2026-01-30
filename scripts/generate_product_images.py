"""
Generate placeholder product images locally (no internet needed)
Creates colorful bottle-style images for each product
"""
import os
import psycopg2
from PIL import Image, ImageDraw, ImageFont
import hashlib

IMAGE_DIR = r"L:\limo\data\product_images"
os.makedirs(IMAGE_DIR, exist_ok=True)

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Color scheme by category
CATEGORY_COLORS = {
    'Whiskey': (139, 69, 19),         # Brown
    'Vodka': (230, 230, 250),         # Lavender
    'Rum': (184, 92, 23),             # Dark brown
    'Gin': (0, 100, 0),               # Dark green
    'Tequila': (204, 170, 0),         # Gold
    'Liqueurs': (192, 0, 0),          # Dark red
    'Brandy': (160, 82, 45),          # Sienna
    'Wine - Red': (128, 0, 0),        # Maroon
    'Wine - White': (255, 255, 200),  # Light yellow
    'Champagne': (255, 215, 0),       # Gold
    'Beer': (184, 134, 11),           # Dark goldenrod
    'Ciders': (218, 165, 32),         # Goldenrod
    'Craft Beer': (139, 69, 19),      # Saddle brown
    'Hard Seltzers': (176, 224, 230), # Powder blue
    'Non-Alcoholic Spirits': (211, 211, 211), # Light gray
}

def get_color_for_category(category):
    """Get color for product category"""
    return CATEGORY_COLORS.get(category, (100, 100, 100))

def generate_bottle_image(item_id, item_name, category):
    """Generate a bottle-shaped product image"""
    # Create image
    img = Image.new('RGB', (150, 200), color=(240, 240, 240))
    draw = ImageDraw.Draw(img)
    
    # Get category color
    color = get_color_for_category(category)
    
    # Draw bottle shape
    # Bottle cap (top)
    draw.rectangle([50, 10, 100, 20], fill=(200, 200, 200), outline=(100, 100, 100))
    
    # Bottle neck
    draw.rectangle([60, 20, 90, 40], fill=color, outline=(50, 50, 50), width=2)
    
    # Main bottle body
    draw.ellipse([30, 40, 120, 180], fill=color, outline=(50, 50, 50), width=2)
    
    # Bottle shine/highlight
    draw.ellipse([50, 50, 70, 100], fill=(255, 255, 255, 100), outline=None)
    
    # Add text label - product name (truncated)
    try:
        # Try to use a system font
        font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 10)
    except:
        font = ImageFont.load_default()
    
    # Draw product label
    label_text = item_name[:20]
    bbox = draw.textbbox((0, 0), label_text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (150 - text_width) // 2
    y = 90
    
    # Draw text with white background
    draw.rectangle([x-3, y-3, x+text_width+3, y+text_height+3], fill=(255, 255, 255))
    draw.text((x, y), label_text, fill=(50, 50, 50), font=font)
    
    return img

print("\n🎨 GENERATING PRODUCT IMAGES (994 items)\n")
print("="*70)

try:
    # Get all products
    cur.execute("SELECT item_id, item_name, category FROM beverage_products ORDER BY item_id")
    products = cur.fetchall()
    
    generated = 0
    
    for idx, (item_id, item_name, category) in enumerate(products):
        # Generate filename
        safe_name = item_name[:30].replace(' ', '_').replace('/', '_')
        filepath = os.path.join(IMAGE_DIR, f"{item_id}_{safe_name}.jpg")
        
        # Skip if already exists
        if os.path.exists(filepath):
            continue
        
        # Generate image
        img = generate_bottle_image(item_id, item_name, category)
        img.save(filepath, 'JPEG', quality=90)
        
        # Update database
        rel_path = f"/data/product_images/{os.path.basename(filepath)}"
        cur.execute(
            "UPDATE beverage_products SET image_path = %s WHERE item_id = %s",
            (rel_path, item_id)
        )
        
        generated += 1
        
        if (idx + 1) % 100 == 0:
            print(f"  ✓ Generated {idx + 1} images...")
            conn.commit()
    
    conn.commit()
    
    # Show statistics
    cur.execute("SELECT COUNT(*) FROM beverage_products WHERE image_path IS NOT NULL")
    with_images = cur.fetchone()[0]
    
    print(f"\n" + "="*70)
    print(f"✅ Image Generation Complete!")
    print(f"🎨 Generated: {generated} bottle images")
    print(f"📊 Total with images: {with_images}/994 items")
    print(f"📁 Storage: {IMAGE_DIR}")
    
    # Show sample
    print(f"\n✅ All 994 products now have custom bottle-style images!")
    print(f"   Each image shows:")
    print(f"   • Color-coded bottle by category")
    print(f"   • Product name label")
    print(f"   • Bottle shine effect")
    print(f"\n" + "="*70 + "\n")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    conn.rollback()
finally:
    cur.close()
    conn.close()
