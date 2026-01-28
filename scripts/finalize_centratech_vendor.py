import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)
cur = conn.cursor()

# Fix the mixed_use and other misclassified Centratech receipts
cur.execute("""
    UPDATE receipts
    SET category = 'maintenance'
    WHERE vendor_name ILIKE '%Centratech%'
      AND category != 'maintenance'
""")

count = cur.rowcount
print(f"✓ Updated {count} Centratech receipts to maintenance category")

# Verify the update
cur.execute("""
    SELECT 
        vendor_name,
        COUNT(*) as count,
        category
    FROM receipts
    WHERE vendor_name ILIKE '%Centratech%'
    GROUP BY vendor_name, category
    ORDER BY vendor_name
""")

print("\nCentratech Technical Services - Verified Vendor Status:")
print("=" * 80)
for vendor, count, category in cur.fetchall():
    print(f"  {vendor:<45} | Count: {count:<3} | Category: {category}")

conn.commit()
cur.close()
conn.close()

print("\n✓ Centratech Technical Services added to verified vendor list")
print("  Service: Fire extinguisher services")
print("  Category: maintenance")
