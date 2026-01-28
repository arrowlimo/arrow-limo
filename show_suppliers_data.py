import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("=" * 80)
print("SUPPLIERS TABLE DATA SAMPLE")
print("=" * 80)

# Get all data (only 784 rows)
cur.execute("SELECT * FROM suppliers LIMIT 20")
rows = cur.fetchall()

print(f"\nFirst 20 rows of 784 total:")
print("-" * 80)
for i, row in enumerate(rows, 1):
    print(f"\nRow {i}:")
    for val in row:
        if val:
            print(f"  {val}")

# Check if there's any useful structure
cur.execute("SELECT COUNT(*) FROM suppliers WHERE \"Arrow Limousine backup 2025\" IS NOT NULL")
non_null = cur.fetchone()[0]
print(f"\nNon-null values in first column: {non_null}")

conn.close()
