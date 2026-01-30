"""Search for comprehensive beverage inventory in all database tables"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("\n🔍 SEARCHING FOR COMPREHENSIVE INVENTORY WITH SIZES\n")
print("="*80)

# Get all tables and search for size-related columns
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema='public'
    ORDER BY table_name
""")

all_tables = [t[0] for t in cur.fetchall()]

# Look for any tables with many rows that might be the 1500-item list
print("\nLARGE TABLES (might contain full inventory):\n")

for table_name in all_tables:
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cur.fetchone()[0]
        
        if count >= 100:  # Show tables with 100+ rows
            # Check if it has size or product-like columns
            cur.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{table_name}'
                AND (column_name ILIKE '%size%' OR column_name ILIKE '%product%' OR column_name ILIKE '%name%')
            """)
            
            size_cols = [c[0] for c in cur.fetchall()]
            
            if size_cols or 'product' in table_name.lower() or 'inventory' in table_name.lower():
                print(f"  📊 {table_name:40} {count:6d} rows  (has: {', '.join(size_cols[:2])})")
    except Exception:
        pass

print("\n" + "="*80)
print("\nCHECKING EXPORT/ARCHIVE LOCATIONS:\n")

# Look for tables that end with _archive or _export
for table_name in all_tables:
    if 'export' in table_name.lower() or 'archive' in table_name.lower():
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cur.fetchone()[0]
            if count > 0:
                print(f"  🗂️ {table_name:50} {count:6d} rows")
        except Exception:
            pass

cur.close()
conn.close()
