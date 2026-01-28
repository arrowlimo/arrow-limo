"""Search database for any beverage/product tables"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("\n🔍 SEARCHING DATABASE FOR BEVERAGE/PRODUCT TABLES\n")
print("=" * 70)

# Find all tables with related names
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema='public'
    AND (
        table_name ILIKE '%beverage%'
        OR table_name ILIKE '%product%'
        OR table_name ILIKE '%inventory%'
        OR table_name ILIKE '%menu%'
        OR table_name ILIKE '%order%'
        OR table_name ILIKE '%cart%'
    )
    ORDER BY table_name
""")

tables = cur.fetchall()

if tables:
    print("Found tables:\n")
    for (table_name,) in tables:
        # Get row count
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cur.fetchone()[0]
        
        # Get column names
        cur.execute(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}'
        """)
        columns = [c[0] for c in cur.fetchall()]
        
        print(f"  📋 {table_name}")
        print(f"     Rows: {count:,}")
        print(f"     Columns: {', '.join(columns[:5])}")
        if len(columns) > 5:
            print(f"             ... and {len(columns)-5} more")
        print()

print("=" * 70)

# Check for any views
print("\nSEARCHING FOR VIEWS:\n")
cur.execute("""
    SELECT table_name 
    FROM information_schema.views 
    WHERE table_schema='public'
    AND (
        table_name ILIKE '%beverage%'
        OR table_name ILIKE '%product%'
        OR table_name ILIKE '%inventory%'
    )
    ORDER BY table_name
""")

views = cur.fetchall()
if views:
    for (view_name,) in views:
        print(f"  👁️ {view_name}")
else:
    print("  (No related views found)")

print("\n" + "=" * 70)

# Check if there are any backup/archive tables
print("\nCHECKING FOR BACKUPS/ARCHIVES:\n")
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema='public'
    AND (
        table_name ILIKE '%backup%'
        OR table_name ILIKE '%archive%'
        OR table_name ILIKE '%old%'
        OR table_name ILIKE '%bak%'
    )
    ORDER BY table_name
""")

backups = cur.fetchall()
if backups:
    print("Found backup/archive tables:\n")
    for (table_name,) in backups:
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cur.fetchone()[0]
        if 'beverage' in table_name.lower() or 'product' in table_name.lower():
            print(f"  🔄 {table_name:40} ({count:,} rows) ⭐ POSSIBLE MATCH")
        else:
            print(f"  🔄 {table_name:40} ({count:,} rows)")
else:
    print("  (No backup tables found)")

print("\n" + "=" * 70)

cur.close()
conn.close()
