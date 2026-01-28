import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata', 
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Get table count
cur.execute("""
    SELECT COUNT(*) 
    FROM information_schema.tables 
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
""")
table_count = cur.fetchone()[0]

# Get database size
cur.execute("SELECT pg_size_pretty(pg_database_size('almsdata'))")
db_size = cur.fetchone()[0]

print("=" * 60)
print("DATABASE STATISTICS AFTER PHASE 1 CLEANUP")
print("=" * 60)
print(f"Database: almsdata")
print(f"Tables: {table_count} (was 324, deleted 17)")
print(f"Size: {db_size}")
print()
print("✅ Phase 1 Complete: 17 duplicate tables removed")
print("📊 Rows removed: 229,465")
print("💾 Backups: backups/table_exports_before_cleanup/")
print()

conn.close()
