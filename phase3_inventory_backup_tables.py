"""Find all backup tables for Phase 3 cleanup"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

# Find backup tables
cur.execute("""
    SELECT tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
    FROM pg_tables 
    WHERE schemaname = 'public' 
    AND (tablename LIKE '%backup%' OR tablename LIKE '%_bak' OR tablename LIKE '%_old')
    ORDER BY tablename
""")
backup_tables = cur.fetchall()

print(f"\n{'='*100}")
print(f"PHASE 3: BACKUP TABLE INVENTORY")
print(f"{'='*100}")
print(f"\nFound {len(backup_tables)} backup/old tables:\n")

total_size_query = """
    SELECT SUM(pg_total_relation_size(schemaname||'.'||tablename))
    FROM pg_tables 
    WHERE schemaname = 'public' 
    AND (tablename LIKE '%backup%' OR tablename LIKE '%_bak' OR tablename LIKE '%_old')
"""
cur.execute(total_size_query)
total_bytes = cur.fetchone()[0] or 0
total_mb = total_bytes / (1024 * 1024)

for table, size in backup_tables[:30]:
    print(f"  {table:<60} {size:>15}")
    
if len(backup_tables) > 30:
    print(f"\n  ... and {len(backup_tables) - 30} more tables")

print(f"\n{'='*100}")
print(f"TOTAL SIZE: {total_mb:.2f} MB ({len(backup_tables)} tables)")
print(f"{'='*100}")

print(f"""
📋 PHASE 3 OPTIONS:
  1. Archive to external storage (pg_dump backup tables only)
  2. Drop all backup tables (after confirming main data is intact)
  3. Keep recent backups, drop old ones (e.g., >90 days)

💡 RECOMMENDATION:
  - Create full database backup first
  - Drop backup tables to free ~{total_mb:.0f} MB
  - Keep SQL dump files for emergency recovery
""")

cur.close()
conn.close()
