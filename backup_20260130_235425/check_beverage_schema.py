"""Check beverage_products schema and link images from L:\limo\data\images"""
import psycopg2
import os
from pathlib import Path

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Get schema
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'beverage_products'
    ORDER BY ordinal_position
""")
print("beverage_products schema:")
for col in cur.fetchall():
    print(f"  {col[0]}: {col[1]} (nullable: {col[2]})")

# Check if images directory exists
image_dir = Path("L:/limo/data/images")
if image_dir.exists():
    images = list(image_dir.glob("*.jpg")) + list(image_dir.glob("*.png"))
    print(f"\n📁 Found {len(images)} images in {image_dir}")
    if images:
        print("Sample images:")
        for img in images[:5]:
            print(f"  {img.name}")
else:
    print(f"\n⚠️ Image directory not found: {image_dir}")

cur.close()
conn.close()
