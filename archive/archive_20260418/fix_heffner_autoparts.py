"""Fix HEFFNER AUTO FINANCE vendor name - remove (Auto-Parts) label and correct categorization"""
import psycopg2
import os
from dotenv import load_dotenv
import traceback

load_dotenv()

try:
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME", "limo"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )
    print("✓ Connected to database")
except Exception as e:
    print(f"✗ Database connection failed: {e}")
    traceback.print_exc()
    exit(1)

cur = conn.cursor()

print("=" * 80)
print("HEFFNER AUTO FINANCE - Fix (Auto-Parts) Miscategorization")
print("=" * 80)

# Step 1: Check for vendor names with "(Auto-Parts)" in them
print("\n1. Checking for HEFFNER vendors with '(Auto-Parts)' in vendor_name...")
cur.execute("""
    SELECT DISTINCT vendor_name, COUNT(*) as count
    FROM receipts
    WHERE vendor_name ILIKE '%HEFFNER%' 
      AND vendor_name LIKE '%(Auto-Parts)%'
    GROUP BY vendor_name
    ORDER BY count DESC
""")
autoparts_vendors = cur.fetchall()

if autoparts_vendors:
    print(f"\n   Found {len(autoparts_vendors)} vendor name(s) with (Auto-Parts) label:")
    total_receipts = 0
    for vendor, count in autoparts_vendors:
        print(f"   - '{vendor}': {count} receipt(s)")
        total_receipts += count
    print(f"\n   Total receipts to fix: {total_receipts}")
else:
    print("   No HEFFNER vendors found with '(Auto-Parts)' label")

# Step 2: Check all HEFFNER vendor name variations
print("\n2. Checking all HEFFNER vendor name variations...")
cur.execute("""
    SELECT DISTINCT vendor_name, COUNT(*) as count
    FROM receipts
    WHERE vendor_name ILIKE '%HEFFNER%'
    GROUP BY vendor_name
    ORDER BY count DESC
""")
all_heffner = cur.fetchall()
print(f"   Found {len(all_heffner)} distinct HEFFNER vendor name(s):")
for vendor, count in all_heffner:
    print(f"   - '{vendor}': {count} receipt(s)")

# Step 3: Fix the vendor names
if autoparts_vendors:
    print("\n3. Preparing to fix vendor names...")
    print("\n   Will perform the following updates:")
    
    for old_vendor, count in autoparts_vendors:
        # Remove (Auto-Parts) and standardize to HEFFNER AUTO FINANCE
        new_vendor = old_vendor.replace("(Auto-Parts)", "").strip()
        # Standardize the name
        if "HEFFNER" in new_vendor.upper():
            new_vendor = "HEFFNER AUTO FINANCE"
        print(f"   - '{old_vendor}' → '{new_vendor}' ({count} receipts)")
    
    confirm = input("\n   Proceed with updates? (yes/no): ").strip().lower()
    
    if confirm == 'yes':
        for old_vendor, count in autoparts_vendors:
            new_vendor = "HEFFNER AUTO FINANCE"
            
            # Update vendor_name and canonical_vendor
            cur.execute("""
                UPDATE receipts
                SET vendor_name = %s,
                    canonical_vendor = %s
                WHERE vendor_name = %s
            """, (new_vendor, new_vendor, old_vendor))
            
            print(f"   ✓ Updated {cur.rowcount} receipt(s): '{old_vendor}' → '{new_vendor}'")
        
        conn.commit()
        print("\n   ✓ All vendor names updated successfully!")
        
        # Step 4: Update categories for HEFFNER receipts that may have wrong category
        print("\n4. Checking and updating receipt categories for HEFFNER...")
        cur.execute("""
            UPDATE receipts
            SET category = 'Vehicle Financing'
            WHERE vendor_name = 'HEFFNER AUTO FINANCE'
              AND (category IS NULL 
                   OR category IN ('Unknown', 'AUTO PARTS/MAINTENANCE', 'Auto Parts'))
        """)
        if cur.rowcount > 0:
            print(f"   ✓ Updated category to 'Vehicle Financing' for {cur.rowcount} receipt(s)")
            conn.commit()
        else:
            print("   No category updates needed")
        
        # Step 5: Update vendor_default_categories if needed
        print("\n5. Updating vendor_default_categories table...")
        cur.execute("""
            INSERT INTO vendor_default_categories 
                (vendor_canonical_name, default_category, default_subcategory, notes)
            VALUES 
                ('HEFFNER AUTO FINANCE', 'Vehicle Financing', 'vehicle_lease', 
                 'Vehicle leasing and financing company')
            ON CONFLICT (vendor_canonical_name) 
            DO UPDATE SET 
                default_category = 'Vehicle Financing',
                default_subcategory = 'vehicle_lease',
                notes = 'Vehicle leasing and financing company',
                updated_at = CURRENT_TIMESTAMP
        """)
        conn.commit()
        print("   ✓ Vendor default category updated")
        
        print("\n" + "=" * 80)
        print("✓ FIX COMPLETE!")
        print("=" * 80)
        print("\nSummary:")
        print(f"  - Updated {total_receipts} receipt(s)")
        print(f"  - Standardized vendor name to: 'HEFFNER AUTO FINANCE'")
        print(f"  - Set default category to: 'Vehicle Financing'")
        print("\nYou may need to refresh the materialized view if it exists:")
        print("  REFRESH MATERIALIZED VIEW mv_vendor_list;")
        
    else:
        print("\n   Updates cancelled.")
else:
    print("\n3. No fixes needed - vendor names are correct")

cur.close()
conn.close()
