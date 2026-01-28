import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Check maintenance_records table
cur.execute("""
    SELECT column_name, data_type, character_maximum_length
    FROM information_schema.columns
    WHERE table_name = 'maintenance_records'
    ORDER BY ordinal_position
""")
cols = cur.fetchall()

print("\n" + "="*60)
print("maintenance_records TABLE SCHEMA")
print("="*60)
if cols:
    for col_name, data_type, max_len in cols:
        len_info = f"({max_len})" if max_len else ""
        print(f"  {col_name:30} {data_type}{len_info}")
else:
    print("  ❌ Table does not exist")

# Check maintenance_activity_types table
cur.execute("""
    SELECT column_name, data_type, character_maximum_length
    FROM information_schema.columns
    WHERE table_name = 'maintenance_activity_types'
    ORDER BY ordinal_position
""")
types_cols = cur.fetchall()

print("\n" + "="*60)
print("maintenance_activity_types TABLE SCHEMA")
print("="*60)
if types_cols:
    for col_name, data_type, max_len in types_cols:
        len_info = f"({max_len})" if max_len else ""
        print(f"  {col_name:30} {data_type}{len_info}")
else:
    print("  ❌ Table does not exist")

# Check existing records
if cols:
    cur.execute("SELECT COUNT(*) FROM maintenance_records")
    count = cur.fetchone()[0]
    print(f"\n  📊 Total records: {count}")
    
    if count > 0:
        cur.execute("""
            SELECT mr.*, v.vehicle_number
            FROM maintenance_records mr
            LEFT JOIN vehicles v ON mr.vehicle_id = v.vehicle_id
            LIMIT 5
        """)
        sample = cur.fetchall()
        print("\n  Sample records:")
        for row in sample:
            print(f"    {row}")

cur.close()
conn.close()
