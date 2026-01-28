"""Link product images to beverage_products table"""
import psycopg2
import os
from pathlib import Path

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Get all images in product_images directory
image_dir = Path("L:/limo/data/product_images")
images = list(image_dir.glob("*.jpg")) + list(image_dir.glob("*.png"))

print(f"Found {len(images)} images in {image_dir}")

# Build a map: item_id -> image_path
image_map = {}
for img_path in images:
    filename = img_path.name
    # Extract item_id from filename (format: <id>_<name>.jpg)
    if '_' in filename:
        try:
            item_id = int(filename.split('_')[0])
            # Store relative path format: /data/product_images/filename.jpg
            rel_path = f"/data/product_images/{filename}"
            image_map[item_id] = rel_path
        except ValueError:
            pass  # Not a numbered file

print(f"Mapped {len(image_map)} images to item IDs")

# Update database
updated = 0
for item_id, image_path in image_map.items():
    cur.execute("""
        UPDATE beverage_products
        SET image_path = %s
        WHERE item_id = %s
    """, (image_path, item_id))
    if cur.rowcount > 0:
        updated += 1

conn.commit()

print(f"✅ Updated {updated} products with image paths")

# Verify
cur.execute("""
    SELECT COUNT(*) as total, COUNT(image_path) as has_image
    FROM beverage_products
""")
stats = cur.fetchone()
print(f"\nVerification:")
print(f"  Total products: {stats[0]}")
print(f"  Has image_path: {stats[1]}")

# Show sample
cur.execute("""
    SELECT item_id, item_name, image_path
    FROM beverage_products
    WHERE image_path IS NOT NULL
    ORDER BY item_id
    LIMIT 10
""")
print(f"\nSample products with images:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1][:30]} -> {row[2]}")

cur.close()
conn.close()
print("\n✅ Done! Restart app to see images.")
