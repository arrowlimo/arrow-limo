"""
Analyze database size and identify staging/temporary tables
"""
import psycopg2
import os

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

def pg_size_pretty(bytes_val):
    """Convert bytes to human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.2f} PB"

# Total database size
cur.execute("SELECT pg_size_pretty(pg_database_size(%s))", (DB_NAME,))
total_size = cur.fetchone()[0]
print(f"\n{'='*80}")
print(f"DATABASE SIZE ANALYSIS: {DB_NAME}")
print(f"{'='*80}")
print(f"Total Size: {total_size}\n")

# Table sizes
cur.execute("""
    SELECT 
        schemaname,
        tablename,
        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
        pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as index_size,
        pg_total_relation_size(schemaname||'.'||tablename) as bytes
    FROM pg_tables
    WHERE schemaname = 'public'
    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
""")
tables = cur.fetchall()

print(f"{'TABLE':<40} {'TOTAL SIZE':<15} {'TABLE':<15} {'INDEXES':<15}")
print(f"{'-'*40} {'-'*15} {'-'*15} {'-'*15}")

total_bytes = 0
for schema, table, total, tbl, idx, bytes_val in tables:
    print(f"{table:<40} {total:<15} {tbl:<15} {idx:<15}")
    total_bytes += bytes_val

print(f"\n{'='*80}")
print(f"Total Data Size: {pg_size_pretty(total_bytes)}")
print(f"{'='*80}\n")

# Identify staging/temporary tables
print(f"{'='*80}")
print(f"STAGING/TEMPORARY TABLES (candidates for exclusion from Neon)")
print(f"{'='*80}\n")

staging_keywords = [
    'staging', 'temp', 'tmp', 'import', 'raw', 'scratch', 
    'backup', 'archive', 'test', 'debug', 'migration',
    'legacy', 'old', 'cache', 'working', 'intermediate'
]

staging_tables = []
for schema, table, total, tbl, idx, bytes_val in tables:
    if any(keyword in table.lower() for keyword in staging_keywords):
        staging_tables.append((table, total, bytes_val))

if staging_tables:
    staging_total = sum(b for _, _, b in staging_tables)
    print(f"{'TABLE':<40} {'SIZE':<15}")
    print(f"{'-'*40} {'-'*15}")
    for table, size, bytes_val in staging_tables:
        print(f"{table:<40} {size:<15}")
    print(f"\nTotal Staging Size: {pg_size_pretty(staging_total)}")
    print(f"Potential Savings: {pg_size_pretty(staging_total)} ({staging_total*100//total_bytes if total_bytes else 0}% of total)")
else:
    print("No obvious staging tables found based on naming patterns.")

# Additional analysis: tables with no recent activity
print(f"\n{'='*80}")
print(f"TABLES WITH NO RECENT DATA (candidates for exclusion)")
print(f"{'='*80}\n")

# Check for tables with date columns
cur.execute("""
    SELECT DISTINCT table_name 
    FROM information_schema.columns 
    WHERE table_schema = 'public' 
    AND (column_name LIKE '%date%' OR column_name LIKE '%created%' OR column_name LIKE '%updated%')
    ORDER BY table_name
""")
date_tables = [row[0] for row in cur.fetchall()]

print("Tables with date tracking (checking for stale data):\n")
stale_candidates = []

for table in date_tables[:20]:  # Check first 20 to avoid timeout
    try:
        # Find date column
        cur.execute(f"""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            AND (column_name LIKE '%%date%%' OR column_name LIKE '%%created%%' OR column_name LIKE '%%updated%%')
            LIMIT 1
        """, (table,))
        result = cur.fetchone()
        if result:
            date_col = result[0]
            cur.execute(f"""
                SELECT COUNT(*), MAX({date_col}::text)
                FROM {table}
                WHERE {date_col} IS NOT NULL
            """)
            count, max_date = cur.fetchone()
            if count and count > 0:
                print(f"  {table:<35} {count:>8} rows | Latest: {max_date or 'N/A'}")
    except Exception as e:
        pass

# Row counts
print(f"\n{'='*80}")
print(f"ROW COUNTS (Top 20 tables)")
print(f"{'='*80}\n")

cur.execute("""
    SELECT schemaname, tablename, 
           pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
    FROM pg_tables
    WHERE schemaname = 'public'
    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
    LIMIT 20
""")
top_tables = cur.fetchall()

print(f"{'TABLE':<40} {'ROWS':<15} {'SIZE':<15}")
print(f"{'-'*40} {'-'*15} {'-'*15}")

for schema, table, size in top_tables:
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"{table:<40} {count:>14,} {size:<15}")
    except Exception as e:
        print(f"{table:<40} {'ERROR':<15} {size:<15}")

cur.close()
conn.close()

print(f"\n{'='*80}")
print(f"RECOMMENDATION:")
print(f"{'='*80}")
print(f"""
For Neon deployment, consider excluding:
1. Staging/import tables (if any found above)
2. Backup/archive tables
3. Test/debug tables
4. Large historical tables that are rarely accessed

Core operational tables to INCLUDE:
- charters, payments, receipts (core business data)
- clients, employees, vehicles (master data)
- banking_transactions (reconciliation)
- users, security_audit (authentication/audit)
""")
