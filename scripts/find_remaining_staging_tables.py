"""
Find all remaining staging/legacy tables (lms_*, limo_*, *_staging, *_temp).
Check record counts, dependencies, and whether they're referenced anywhere.
"""
import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("=" * 80)
print("REMAINING STAGING/LEGACY TABLES")
print("=" * 80)

# Find all staging/legacy tables
cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_type = 'BASE TABLE'
    AND (
        table_name LIKE 'lms_%'
        OR table_name LIKE 'limo_%'
        OR table_name LIKE '%_staging%'
        OR table_name LIKE '%_temp%'
        OR table_name LIKE '%_backup%'
        OR table_name LIKE '%_archive%'
        OR table_name LIKE 'qb_%'
    )
    ORDER BY table_name
""")
tables = [row[0] for row in cur.fetchall()]

if not tables:
    print("\n✅ NO STAGING TABLES FOUND - Database is clean!")
else:
    print(f"\nFound {len(tables)} staging/legacy tables:\n")
    
    for table_name in tables:
        # Get record count
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cur.fetchone()[0]
        
        # Check for foreign key references
        cur.execute("""
            SELECT COUNT(*)
            FROM information_schema.table_constraints tc
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND ccu.table_name = %s
        """, (table_name,))
        fk_refs = cur.fetchone()[0]
        
        # Check for view dependencies
        cur.execute("""
            SELECT COUNT(*)
            FROM information_schema.view_table_usage
            WHERE table_name = %s
        """, (table_name,))
        view_deps = cur.fetchone()[0]
        
        deps = []
        if fk_refs > 0:
            deps.append(f"{fk_refs} FK")
        if view_deps > 0:
            deps.append(f"{view_deps} views")
        
        dep_str = f" ({', '.join(deps)})" if deps else ""
        
        print(f"  • {table_name:50} {count:>8,} records{dep_str}")

# Check for any views using staging tables
print("\n" + "=" * 80)
print("VIEWS USING STAGING TABLES")
print("=" * 80)

if tables:
    placeholders = ','.join(['%s'] * len(tables))
    cur.execute(f"""
        SELECT DISTINCT view_name, table_name
        FROM information_schema.view_table_usage
        WHERE table_name IN ({placeholders})
        ORDER BY view_name, table_name
    """, tables)
    
    view_deps = cur.fetchall()
    if view_deps:
        print()
        for view_name, table_name in view_deps:
            print(f"  • {view_name} → {table_name}")
    else:
        print("\n✅ No views depend on staging tables")
else:
    print("\n✅ No staging tables to check")

# Summary
print("\n" + "=" * 80)
print("TOTAL TABLE COUNT")
print("=" * 80)
cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'")
total = cur.fetchone()[0]
print(f"\nDatabase has {total} base tables")
if tables:
    print(f"  - Staging/legacy: {len(tables)}")
    print(f"  - Production: {total - len(tables)}")

cur.close()
conn.close()
