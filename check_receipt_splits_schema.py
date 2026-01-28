import psycopg2

conn = psycopg2.connect(
    host='localhost', 
    database='almsdata', 
    user='postgres', 
    password='***REMOVED***'
)
cur = conn.cursor()

# Check if receipt_splits table exists
cur.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'receipt_splits'
    )
""")
exists = cur.fetchone()[0]
print(f"receipt_splits table exists: {exists}")

if exists:
    # Get columns
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name='receipt_splits' 
        ORDER BY ordinal_position
    """)
    columns = cur.fetchall()
    print("\nColumns in receipt_splits:")
    for col_name, col_type in columns:
        print(f"  - {col_name}: {col_type}")
    
    # Get sample data
    cur.execute("SELECT * FROM receipt_splits LIMIT 3")
    print(f"\nSample data (first 3 rows):")
    for row in cur.fetchall():
        print(f"  {row}")
else:
    print("\nreceipt_splits table does NOT exist!")

cur.close()
conn.close()
