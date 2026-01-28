import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

# Database size
cur.execute("SELECT pg_size_pretty(pg_database_size('almsdata'))")
db_size = cur.fetchone()[0]
print(f"Database size: {db_size}")

# Top 15 largest tables
cur.execute("""
    SELECT 
        schemaname, 
        tablename, 
        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
        pg_total_relation_size(schemaname||'.'||tablename) AS bytes
    FROM pg_tables 
    WHERE schemaname = 'public' 
    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC 
    LIMIT 15
""")

print("\nTop 15 largest tables:")
for i, row in enumerate(cur.fetchall()):
    print(f"{i+1:2}. {row[1]:40} {row[2]:>12}")

# Table and view count
cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")
table_count = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM information_schema.views WHERE table_schema='public'")
view_count = cur.fetchone()[0]

print(f"\nTables: {table_count}, Views: {view_count}")

# Record counts for key tables
print("\nKey table record counts:")
key_tables = [
    'charters', 'clients', 'payments', 'receipts', 
    'banking_transactions', 'general_ledger', 'unified_general_ledger',
    'employees', 'vehicles'
]

for table in key_tables:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    print(f"  {table:30} {count:>8,}")

cur.close()
conn.close()
