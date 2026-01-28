"""
Empty/Null Column Audit - Find wasted space
Identifies columns with no data, low cardinality, and space waste
"""
import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

print("=" * 100)
print("EMPTY/NULL COLUMN AUDIT - Finding Wasted Space")
print("=" * 100)

# Get all active tables (not backups)
cur.execute("""
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_type = 'BASE TABLE'
AND table_name NOT LIKE '%backup%'
AND table_name NOT LIKE '%_archived%'
ORDER BY table_name
""")
tables = [row[0] for row in cur.fetchall()]
print(f"\nScanning {len(tables)} active tables for empty columns...\n")

empty_columns = []
low_cardinality = []
total_waste = 0

for table in tables:
    try:
        # Get row count
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        row_count = cur.fetchone()[0]
        
        if row_count == 0:
            # Skip empty tables
            continue
        
        # Get columns
        cur.execute(f"""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = '{table}'
        ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        
        for col_name, col_type in columns:
            try:
                # Count non-null values
                cur.execute(f"""
                SELECT COUNT(*)
                FROM {table}
                WHERE "{col_name}" IS NOT NULL
                """)
                not_null_count = cur.fetchone()[0]
                null_count = row_count - not_null_count
                null_percent = (null_count / row_count * 100) if row_count > 0 else 0
                
                # If column is completely empty
                if not_null_count == 0:
                    # Estimate space waste
                    if col_type in ('text', 'character varying'):
                        bytes_per_row = 50  # Average VARCHAR overhead
                    elif col_type in ('numeric', 'double precision'):
                        bytes_per_row = 16
                    elif col_type in ('integer', 'bigint'):
                        bytes_per_row = 8
                    elif col_type == 'boolean':
                        bytes_per_row = 1
                    else:
                        bytes_per_row = 20
                    
                    total_bytes = bytes_per_row * row_count
                    total_mb = total_bytes / 1024 / 1024
                    
                    empty_columns.append({
                        'table': table,
                        'column': col_name,
                        'type': col_type,
                        'rows': row_count,
                        'null_rows': null_count,
                        'wasted_mb': total_mb
                    })
                    total_waste += total_mb
                
                # Low cardinality (very few unique values)
                elif not_null_count > 0 and null_percent > 50:
                    cur.execute(f"""
                    SELECT COUNT(DISTINCT "{col_name}")
                    FROM {table}
                    WHERE "{col_name}" IS NOT NULL
                    """)
                    unique_count = cur.fetchone()[0]
                    
                    low_cardinality.append({
                        'table': table,
                        'column': col_name,
                        'type': col_type,
                        'rows': row_count,
                        'not_null': not_null_count,
                        'null_percent': null_percent,
                        'unique_values': unique_count
                    })
            except Exception as e:
                pass  # Skip columns that cause errors
    except Exception as e:
        pass  # Skip tables that cause errors

# Sort by waste
empty_columns.sort(key=lambda x: x['wasted_mb'], reverse=True)
low_cardinality.sort(key=lambda x: x['null_percent'], reverse=True)

print("=" * 100)
print("[1] COMPLETELY EMPTY COLUMNS (0% data, wasting space)")
print("=" * 100)
print(f"Found {len(empty_columns)} completely empty columns\n")

if empty_columns:
    print(f"{'Table':<40} {'Column':<30} {'Type':<20} {'Wasted MB':<12}")
    print("-" * 100)
    for col in empty_columns[:30]:
        print(f"{col['table']:<40} {col['column']:<30} {col['type']:<20} {col['wasted_mb']:.2f} MB")
    
    if len(empty_columns) > 30:
        print(f"... and {len(empty_columns) - 30} more")
    
    print(f"\n💾 TOTAL WASTED SPACE: {total_waste:.2f} MB")
    print(f"\n🎯 ACTION: These columns should be DROPPED immediately")
else:
    print("✅ No completely empty columns found\n")

print("\n" + "=" * 100)
print("[2] MOSTLY EMPTY COLUMNS (>50% NULL, poor data quality)")
print("=" * 100)
print(f"Found {len(low_cardinality)} columns that are >50% NULL\n")

if low_cardinality:
    print(f"{'Table':<40} {'Column':<25} {'NULL %':<12} {'Not Null Rows':<15} {'Unique Values':<15}")
    print("-" * 100)
    for col in low_cardinality[:30]:
        print(f"{col['table']:<40} {col['column']:<25} {col['null_percent']:.1f}% {col['not_null']:<15} {col['unique_values']:<15}")
    
    if len(low_cardinality) > 30:
        print(f"... and {len(low_cardinality) - 30} more")
    
    print(f"\n⚠️ ACTION: Review if these columns are still needed")
else:
    print("✅ No mostly-empty columns found\n")

print("\n" + "=" * 100)
print("[3] DETAILED ANALYSIS - Top 10 Waste by Table")
print("=" * 100)

# Group by table
waste_by_table = {}
for col in empty_columns:
    if col['table'] not in waste_by_table:
        waste_by_table[col['table']] = {'count': 0, 'total_waste': 0, 'columns': []}
    waste_by_table[col['table']]['count'] += 1
    waste_by_table[col['table']]['total_waste'] += col['wasted_mb']
    waste_by_table[col['table']]['columns'].append(col['column'])

sorted_tables = sorted(waste_by_table.items(), key=lambda x: x[1]['total_waste'], reverse=True)

for table, info in sorted_tables[:10]:
    print(f"\n{table}: {info['count']} empty columns, {info['total_waste']:.2f} MB wasted")
    for col_name in info['columns'][:5]:
        print(f"  - {col_name}")
    if len(info['columns']) > 5:
        print(f"  - ... and {len(info['columns']) - 5} more")

print("\n" + "=" * 100)
print("[4] DROP SCRIPTS (Ready to execute)")
print("=" * 100)
print("\n-- WARNING: Review before executing!\n")

if empty_columns:
    print("-- Drop completely empty columns (SAFE):")
    for col in empty_columns[:10]:
        print(f"ALTER TABLE {col['table']} DROP COLUMN {col['column']};")
    
    if len(empty_columns) > 10:
        print(f"\n-- ... and {len(empty_columns) - 10} more (see full script)")

# Detailed per-table analysis
print("\n" + "=" * 100)
print("[5] PER-TABLE ANALYSIS - Core Tables")
print("=" * 100)

core_tables = ['receipts', 'payments', 'charters', 'banking_transactions']

for table in core_tables:
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        row_count = cur.fetchone()[0]
        
        print(f"\n📊 {table.upper()} ({row_count:,} rows)")
        print("-" * 80)
        
        cur.execute(f"""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = '{table}'
        ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        
        table_empty = []
        table_sparse = []
        
        for col_name, col_type in columns:
            try:
                cur.execute(f"""
                SELECT COUNT(*), COUNT(DISTINCT "{col_name}")
                FROM {table}
                WHERE "{col_name}" IS NOT NULL
                """)
                result = cur.fetchone()
                not_null = result[0] if result else 0
                unique = result[1] if result else 0
                null_count = row_count - not_null
                null_percent = (null_count / row_count * 100) if row_count > 0 else 0
                
                if not_null == 0:
                    table_empty.append((col_name, col_type))
                elif null_percent > 80:
                    table_sparse.append((col_name, col_type, null_percent, unique))
            except:
                pass
        
        if table_empty:
            print(f"  🔴 EMPTY ({len(table_empty)} columns):")
            for col_name, col_type in table_empty:
                print(f"     - {col_name} ({col_type})")
        
        if table_sparse:
            print(f"  🟡 SPARSE >80% NULL ({len(table_sparse)} columns):")
            for col_name, col_type, null_pct, unique in table_sparse:
                print(f"     - {col_name} ({col_type}): {null_pct:.0f}% NULL, {unique} unique")
        
        if not table_empty and not table_sparse:
            print("  ✅ All columns have good data coverage")
    except Exception as e:
        print(f"  Error analyzing {table}: {e}")

print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"""
Empty Columns Found: {len(empty_columns)}
  Total Wasted Space: {total_waste:.2f} MB
  
Sparse Columns (>50% NULL): {len(low_cardinality)}

RECOMMENDED ACTIONS:
1. Drop {len(empty_columns)} completely empty columns → Save {total_waste:.2f} MB
2. Investigate {len(low_cardinality)} sparse columns (may be dead code)
3. Use schema_validator.py to verify before dropping
4. Run: DROP TABLE backup tables (saved 100+ MB)

PRIORITY:
1. Drop completely empty columns (SAFE, no data loss)
2. Review sparse columns (may be needed for future features)
3. Archive backups (biggest space saving: ~5+ GB)
""")

cur.close()
conn.close()
