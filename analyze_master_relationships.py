import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("=" * 80)
print("MASTER_RELATIONSHIPS TABLE ANALYSIS")
print("=" * 80)
print()

# Get table structure
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'master_relationships'
    ORDER BY ordinal_position
""")
columns = cur.fetchall()

print("Table Structure:")
for col, dtype, nullable in columns:
    print(f"  {col:<35} {dtype:<20} NULL={nullable}")

print()

# Get row count
cur.execute("SELECT COUNT(*) FROM master_relationships")
row_count = cur.fetchone()[0]
print(f"Total Rows: {row_count:,}")

# Get sample data
cur.execute("SELECT * FROM master_relationships LIMIT 5")
sample = cur.fetchall()

print(f"\nSample Data (first 5 rows):")
print("-" * 80)
for i, row in enumerate(sample, 1):
    print(f"\nRow {i}:")
    for j, val in enumerate(row):
        col_name = columns[j][0]
        print(f"  {col_name}: {val}")

# Check for NULL values
print()
print("NULL Value Analysis:")
print("-" * 80)
for col, dtype, nullable in columns:
    cur.execute(f"SELECT COUNT(*) FROM master_relationships WHERE {col} IS NULL")
    null_count = cur.fetchone()[0]
    if null_count > 0:
        pct = (null_count / row_count) * 100
        print(f"  {col:<35} {null_count:>10,} NULLs ({pct:.1f}%)")

# Check for duplicates
print()
print("Duplicate Analysis:")
print("-" * 80)

# Get all non-id columns to check for duplicates
non_id_cols = [col[0] for col in columns if not col[0].endswith('_id') or col[0] == 'id']
if non_id_cols:
    cols_str = ', '.join(non_id_cols[:5])  # Check first 5 non-id columns
    cur.execute(f"""
        SELECT {cols_str}, COUNT(*) as cnt
        FROM master_relationships
        GROUP BY {cols_str}
        HAVING COUNT(*) > 1
        LIMIT 5
    """)
    dupes = cur.fetchall()
    if dupes:
        print(f"Found duplicate records:")
        for dupe in dupes:
            print(f"  {dupe}")
    else:
        print("  ✅ No duplicates found")

# Check foreign key relationships
print()
print("Foreign Key Validation:")
print("-" * 80)

# Check if referenced tables exist
for col, dtype, nullable in columns:
    if col.endswith('_id') and col != 'id':
        # Try to guess the referenced table name
        table_name = col.replace('_id', 's')  # Try plural first
        
        # Check if table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = %s
            )
        """, (table_name,))
        
        if not cur.fetchone()[0]:
            # Try without 's'
            table_name = col.replace('_id', '')
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (table_name,))
        
        table_exists = cur.fetchone()[0]
        
        if table_exists:
            # Check for orphaned references
            cur.execute(f"""
                SELECT COUNT(*) 
                FROM master_relationships mr
                WHERE mr.{col} IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM {table_name} t
                    WHERE t.{col.replace('_id', '_id' if col in ['charter_id', 'client_id'] else col)} = mr.{col}
                )
            """)
            orphaned = cur.fetchone()[0]
            
            if orphaned > 0:
                pct = (orphaned / row_count) * 100
                print(f"  ⚠ {col} → {table_name}: {orphaned:,} orphaned ({pct:.1f}%)")
            else:
                print(f"  ✅ {col} → {table_name}: All valid")
        else:
            print(f"  ❓ {col} → No matching table found")

conn.close()
