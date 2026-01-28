import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Check vehicles table columns
cur.execute("""
    SELECT column_name, data_type, character_maximum_length
    FROM information_schema.columns
    WHERE table_name = 'vehicles'
    ORDER BY ordinal_position
""")
cols = cur.fetchall()

print("\n" + "="*60)
print("VEHICLES TABLE SCHEMA")
print("="*60)
for col_name, data_type, max_len in cols:
    len_info = f"({max_len})" if max_len else ""
    print(f"  {col_name:30} {data_type}{len_info}")

# Check for status column
cur.execute("""
    SELECT COUNT(*) FROM information_schema.columns
    WHERE table_name = 'vehicles' AND column_name = 'status'
""")
has_status = cur.fetchone()[0] > 0

if has_status:
    cur.execute("SELECT DISTINCT status FROM vehicles WHERE status IS NOT NULL ORDER BY status")
    statuses = cur.fetchall()
    print("\n" + "="*60)
    print("EXISTING VEHICLE STATUSES")
    print("="*60)
    for status in statuses:
        cur.execute("SELECT COUNT(*) FROM vehicles WHERE status = %s", (status[0],))
        count = cur.fetchone()[0]
        print(f"  {status[0]:20} ({count} vehicles)")
    
    # Check NULL status count
    cur.execute("SELECT COUNT(*) FROM vehicles WHERE status IS NULL")
    null_count = cur.fetchone()[0]
    if null_count > 0:
        print(f"  {'(NULL)':20} ({null_count} vehicles)")
else:
    print("\n❌ No 'status' column exists in vehicles table")
    print("   Need to add: ALTER TABLE vehicles ADD COLUMN status VARCHAR(20) DEFAULT 'active';")

cur.close()
conn.close()
