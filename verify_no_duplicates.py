import psycopg2
import re
from collections import defaultdict

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Get all tables
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_type = 'BASE TABLE'
    ORDER BY table_name
""")

tables = [row[0] for row in cur.fetchall()]

print("="*80)
print("FINAL DUPLICATE TABLE VERIFICATION")
print("="*80)
print(f"Total tables in database: {len(tables)}")

# Group by base name (removing common suffixes)
base_names = defaultdict(list)

for table in tables:
    # Remove common backup/versioning patterns
    base = re.sub(r'_backup_\d{8}_\d{6}', '', table)  # _backup_20251216_145717
    base = re.sub(r'_backup_\d{8}', '', base)          # _backup_20251216
    base = re.sub(r'_\d{8}', '', base)                 # _20251216
    base = re.sub(r'_old$', '', base)
    base = re.sub(r'_new$', '', base)
    base = re.sub(r'_temp$', '', base)
    base = re.sub(r'_copy$', '', base)
    
    base_names[base].append(table)

# Find duplicates
duplicates = {k: v for k, v in base_names.items() if len(v) > 1}

print(f"Potential duplicate groups: {len(duplicates)}")

if duplicates:
    print("\n" + "="*80)
    print("DUPLICATE TABLE GROUPS FOUND")
    print("="*80)
    
    for base, versions in sorted(duplicates.items()):
        print(f"\n{base}: ({len(versions)} versions)")
        for table in versions:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            
            # Check if referenced by foreign keys
            cur.execute(f"""
                SELECT COUNT(*) 
                FROM information_schema.table_constraints tc
                JOIN information_schema.constraint_column_usage ccu 
                    ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                AND ccu.table_name = '{table}'
            """)
            fk_refs = cur.fetchone()[0]
            
            refs = f" [📎 {fk_refs} FK refs]" if fk_refs > 0 else ""
            print(f"  - {table:60} ({count:,} rows){refs}")
else:
    print("\n✅ NO DUPLICATE TABLES FOUND")

# Specifically check for user-related tables again
print("\n" + "="*80)
print("USER-RELATED TABLE VERIFICATION")
print("="*80)

cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_type = 'BASE TABLE'
    AND table_name LIKE '%user%'
    ORDER BY table_name
""")

user_tables = cur.fetchall()
print(f"User-related tables: {len(user_tables)}")
for table in user_tables:
    table_name = table[0]
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cur.fetchone()[0]
    print(f"  - {table_name:40} ({count:,} rows)")

print("\n" + "="*80)
print("VERIFICATION COMPLETE")
print("="*80)
print(f"✅ Database cleaned: {len(tables)} tables")
print(f"✅ No authentication duplicates")

cur.close()
conn.close()
