import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Check suppliers table structure
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name='suppliers' 
    ORDER BY ordinal_position
""")
cols = cur.fetchall()

print("Suppliers table columns:")
for col in cols:
    print(f"  - {col[0]} ({col[1]})")

# Check for existing ID column or unique constraints
cur.execute("SELECT * FROM suppliers LIMIT 3")
rows = cur.fetchall()

print("\nSample data:")
for row in rows:
    print(row)

# Check if vendor_name is unique
cur.execute("""
    SELECT COUNT(*) as total,
           COUNT(DISTINCT vendor_name) as distinct_names
    FROM suppliers
""")
total, distinct = cur.fetchone()
print(f"\nTotal rows: {total}")
print(f"Distinct vendor names: {distinct}")
print(f"Unique: {'YES' if total == distinct else 'NO'}")

conn.close()
