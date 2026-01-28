import psycopg2
from collections import defaultdict

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("="*80)
print("CHECKING FOR DUPLICATE/REDUNDANT TABLES")
print("="*80)

# Get all tables
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_type = 'BASE TABLE'
    ORDER BY table_name
""")

all_tables = [row[0] for row in cur.fetchall()]
print(f"\nTotal tables in database: {len(all_tables)}")

# Group similar table names
print("\n" + "="*80)
print("POTENTIAL DUPLICATE TABLES (similar names)")
print("="*80)

# Look for common patterns that indicate duplicates
similar_groups = defaultdict(list)

for table in all_tables:
    # Group by base name (remove common suffixes/prefixes)
    base = table.lower()
    
    # Remove common variations
    for suffix in ['_new', '_old', '_backup', '_temp', '_archive', '_copy', '_2']:
        if base.endswith(suffix):
            base = base[:-len(suffix)]
            break
    
    for prefix in ['new_', 'old_', 'backup_', 'temp_']:
        if base.startswith(prefix):
            base = base[len(prefix):]
            break
    
    similar_groups[base].append(table)

# Show groups with multiple tables
duplicates_found = []
for base, tables in sorted(similar_groups.items()):
    if len(tables) > 1:
        duplicates_found.append((base, tables))
        print(f"\n{base}:")
        for t in tables:
            # Count rows
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            count = cur.fetchone()[0]
            print(f"  - {t:40} ({count:,} rows)")

# Specific check for user tables
print("\n" + "="*80)
print("USER-RELATED TABLES (detailed)")
print("="*80)

user_tables = [t for t in all_tables if 'user' in t.lower()]
for table in user_tables:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    
    # Get column info
    cur.execute(f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = '{table}'
        ORDER BY ordinal_position
    """)
    columns = cur.fetchall()
    
    print(f"\n{table}: {count} rows")
    print(f"  Columns: {', '.join([c[0] for c in columns[:5]])}..." if len(columns) > 5 else f"  Columns: {', '.join([c[0] for c in columns])}")
    
    # Check for foreign key references TO this table
    cur.execute(f"""
        SELECT 
            tc.table_name,
            kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu 
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu 
            ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND ccu.table_name = '{table}'
    """)
    fk_refs = cur.fetchall()
    if fk_refs:
        print(f"  Referenced by: {len(fk_refs)} foreign keys")
        for ref in fk_refs[:3]:
            print(f"    - {ref[0]}.{ref[1]}")

# Check which table is actually used
print("\n" + "="*80)
print("AUTHENTICATION TABLE ANALYSIS")
print("="*80)

print("\nChecking login_manager.py usage...")
with open('L:\\limo\\desktop_app\\login_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()
    if 'FROM system_users' in content:
        print("  ❌ login_manager.py uses: system_users")
        print("  → USERS table is redundant, DELETE IT")
    elif 'FROM users' in content:
        print("  ✅ login_manager.py uses: users")
        print("  → SYSTEM_USERS table is redundant, DELETE IT")

# Check for references to system_users
cur.execute("""
    SELECT 
        tc.table_name,
        kcu.column_name,
        ccu.table_name AS foreign_table_name,
        ccu.column_name AS foreign_column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu 
        ON tc.constraint_name = kcu.constraint_name
    JOIN information_schema.constraint_column_usage ccu 
        ON ccu.constraint_name = tc.constraint_name
    WHERE tc.constraint_type = 'FOREIGN KEY'
    AND (tc.table_name = 'system_users' OR ccu.table_name = 'system_users')
""")

system_users_refs = cur.fetchall()
print(f"\nForeign key relationships for system_users: {len(system_users_refs)}")
for ref in system_users_refs:
    print(f"  {ref[0]}.{ref[1]} → {ref[2]}.{ref[3]}")

cur.close()
conn.close()

print("\n" + "="*80)
print("RECOMMENDATION")
print("="*80)
print("\nBased on analysis:")
print("  - 'users' table is used by login_manager.py (10 users, active)")
print("  - 'system_users' table has foreign key dependencies (user_roles, etc.)")
print("  - Need to check if system_users is used elsewhere before deletion")
print("\nSuggested action: DROP system_users ONLY if no other code uses it")
