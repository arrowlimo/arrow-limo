import psycopg2

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
    host="localhost"
)
cur = conn.cursor()

# Check a specific vendor name
cur.execute("""
    SELECT vendor_name, LENGTH(vendor_name), 
           position('nsf' in LOWER(vendor_name)),
           position('NSF' in vendor_name),
           position('Nsf' in vendor_name)
    FROM receipts 
    WHERE vendor_name = 'EMAIL TRANSFER - MIKE WOODROW'
    LIMIT 1
""")

result = cur.fetchone()
if result:
    name, length, pos_lower, pos_upper, pos_title = result
    print(f"Vendor: {name!r}")
    print(f"Length: {length}")
    print(f"Position of 'nsf' (lowercase): {pos_lower}")
    print(f"Position of 'NSF' (uppercase): {pos_upper}")
    print(f"Position of 'Nsf' (titlecase): {pos_title}")
    print(f"Character codes: {[ord(c) for c in name]}")
else:
    print("No results found")

# Check if pattern actually matches
cur.execute("""
    SELECT vendor_name
    FROM receipts 
    WHERE vendor_name = 'EMAIL TRANSFER - MIKE WOODROW'
    AND vendor_name ILIKE '%NSF%'
    LIMIT 1
""")

if cur.fetchone():
    print("\n✅ ILIKE '%NSF%' DOES match this vendor")
else:
    print("\n❌ ILIKE '%NSF%' does NOT match this vendor")

# Check actual NSF FEE entries
cur.execute("""
    SELECT vendor_name, COUNT(*) 
    FROM receipts 
    WHERE vendor_name ILIKE '%NSF%'
    AND vendor_name NOT LIKE 'EMAIL TRANSFER%'
    GROUP BY vendor_name
    ORDER BY COUNT(*) DESC
""")

print("\nNon-EMAIL-TRANSFER NSF matches:")
for name, count in cur.fetchall():
    print(f"  {name}: {count}")

conn.close()
