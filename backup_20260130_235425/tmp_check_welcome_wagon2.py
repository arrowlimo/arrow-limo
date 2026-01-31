import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='ArrowLimousine'
)

cur = conn.cursor()

# First, get the column names
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'receipts' 
    ORDER BY ordinal_position
""")

columns = [r[0] for r in cur.fetchall()]
print("Available columns in receipts table:")
print(', '.join(columns))
print("\n" + "="*80 + "\n")

# Now query Welcome Wagon receipts with all columns
cur.execute("""
    SELECT * 
    FROM receipts 
    WHERE vendor_name ILIKE '%welcome wagon%' 
    ORDER BY receipt_date, receipt_id
""")

rows = cur.fetchall()

print(f"Found {len(rows)} Welcome Wagon receipts:\n")

for row in rows:
    print(f"Receipt ID: {row[0]}")
    for i, col in enumerate(columns):
        if row[i] is not None and row[i] != '':
            print(f"  {col}: {row[i]}")
    print()

cur.close()
conn.close()
