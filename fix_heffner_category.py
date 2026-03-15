"""Fix HEFFNER vendor category in vendor_default_categories table"""
import psycopg2
import os
from dotenv import load_dotenv
import sys

load_dotenv()

print("Starting script...", flush=True)

try:
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME", "limo"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )
    print("Database connected!", flush=True)
except Exception as e:
    print(f"ERROR connecting to database: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

cur = conn.cursor()

print("=" * 80)
print("HEFFNER Vendor Category Fix")
print("=" * 80)

# Check current vendor_default_categories entries
print("\n1. Current vendor_default_categories for HEFFNER:")
cur.execute("""
    SELECT vendor_canonical_name, default_category, default_subcategory, notes
    FROM vendor_default_categories
    WHERE vendor_canonical_name ILIKE '%HEFFNER%'
""")
results = cur.fetchall()
if results:
    for row in results:
        print(f"   Vendor: {row[0]}")
        print(f"   Category: {row[1]}")
        print(f"   Subcategory: {row[2]}")
        print(f"   Notes: {row[3]}")
        print()
else:
    print("   No HEFFNER entries found")

# Check what the actual vendor names are in receipts
print("2. Most common HEFFNER vendor name in receipts:")
cur.execute("""
    SELECT vendor_name, COUNT(*) as count
    FROM receipts
    WHERE vendor_name ILIKE '%HEFFNER%'
    GROUP BY vendor_name
    ORDER BY count DESC
    LIMIT 1
""")
most_common = cur.fetchone()
if most_common:
    print(f"   '{most_common[0]}': {most_common[1]} receipts")
else:
    print("   No HEFFNER receipts found")

# Fix the vendor category
print("\n3. Fixing vendor_default_categories...")

# Delete old HEFFNER AUTO entry if it exists
cur.execute("""
    DELETE FROM vendor_default_categories
    WHERE vendor_canonical_name = 'HEFFNER AUTO'
""")
if cur.rowcount > 0:
    print(f"   ✓ Removed old 'HEFFNER AUTO' entry")

# Insert/Update the correct entry
cur.execute("""
    INSERT INTO vendor_default_categories 
        (vendor_canonical_name, default_category, default_subcategory, notes, allows_splits)
    VALUES 
        ('HEFFNER AUTO FINANCE', 'Vehicle Financing', 'vehicle_lease', 
         'Vehicle leasing and financing company - NOT auto parts', false)
    ON CONFLICT (vendor_canonical_name) 
    DO UPDATE SET 
        default_category = 'Vehicle Financing',
        default_subcategory = 'vehicle_lease',
        notes = 'Vehicle leasing and financing company - NOT auto parts',
        allows_splits = false,
        updated_at = CURRENT_TIMESTAMP
""")
conn.commit()
print("   ✓ Updated 'HEFFNER AUTO FINANCE' category to 'Vehicle Financing'")

# Verify the change
print("\n4. Verifying changes:")
cur.execute("""
    SELECT vendor_canonical_name, default_category, default_subcategory, notes
    FROM vendor_default_categories
    WHERE vendor_canonical_name ILIKE '%HEFFNER%'
""")
results = cur.fetchall()
if results:
    for row in results:
        print(f"   Vendor: {row[0]}")
        print(f"   Category: {row[1]}")
        print(f"   Subcategory: {row[2]}")
        print(f"   Notes: {row[3]}")

# Check if materialized view exists and needs refresh
cur.execute("""
    SELECT EXISTS (
        SELECT FROM pg_matviews
        WHERE schemaname = 'public' 
        AND matviewname = 'mv_vendor_list'
    )
""")
if cur.fetchone()[0]:
    print("\n5. Refreshing materialized view...")
    cur.execute("REFRESH MATERIALIZED VIEW mv_vendor_list")
    conn.commit()
    print("   ✓ Materialized view refreshed")

print("\n" + "=" * 80)
print("✓ FIX COMPLETE!")
print("=" * 80)
print("\nThe vendor category has been corrected in the database.")
print("The desktop application should now show:")
print("  'HEFFNER AUTO FINANCE (Vehicle Financing)'")
print("instead of:")
print("  'HEFFNER AUTO FINANCE (Auto-Parts)'")
print("\nYou may need to restart the desktop application for changes to take effect.")

cur.close()
conn.close()
