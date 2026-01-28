"""
Comprehensive Database Schema Audit
Scans all tables, views, columns, foreign keys, indexes
Creates detailed inventory for standardization and error prevention
"""
import os
import json
import psycopg2
from collections import defaultdict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

schema_data = {
    "tables": {},
    "views": {},
    "foreign_keys": [],
    "indexes": [],
    "sequences": [],
    "issues": []
}

print("=" * 80)
print("DATABASE SCHEMA AUDIT - almsdata")
print("=" * 80)

# Get all tables
print("\n[1/5] Scanning TABLES...")
cur.execute("""
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name
""")
tables = [row[0] for row in cur.fetchall()]
print(f"Found {len(tables)} tables")

for table in tables:
    schema_data["tables"][table] = {
        "columns": {},
        "row_count": 0,
        "size_mb": 0
    }
    
    # Get columns
    cur.execute("""
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns 
    WHERE table_name = %s
    ORDER BY ordinal_position
    """, (table,))
    
    for col in cur.fetchall():
        col_name, data_type, nullable, default = col
        schema_data["tables"][table]["columns"][col_name] = {
            "type": data_type,
            "nullable": nullable == 'YES',
            "default": default
        }
    
    # Get row count
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        schema_data["tables"][table]["row_count"] = cur.fetchone()[0]
    except:
        pass
    
    # Get size
    try:
        cur.execute("""
        SELECT pg_total_relation_size(%s) / 1024 / 1024
        """, (table,))
        schema_data["tables"][table]["size_mb"] = float(cur.fetchone()[0])
    except:
        pass

# Get all views
print("[2/5] Scanning VIEWS...")
cur.execute("""
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' AND table_type = 'VIEW'
ORDER BY table_name
""")
views = [row[0] for row in cur.fetchall()]
print(f"Found {len(views)} views")

for view in views:
    schema_data["views"][view] = {
        "columns": {}
    }
    
    cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns 
    WHERE table_name = %s
    ORDER BY ordinal_position
    """, (view,))
    
    for col in cur.fetchall():
        col_name, data_type = col
        schema_data["views"][view]["columns"][col_name] = data_type

# Get foreign keys
print("[3/5] Scanning FOREIGN KEYS...")
cur.execute("""
SELECT 
    tc.table_name, 
    kcu.column_name, 
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
ORDER BY tc.table_name, kcu.column_name
""")

for row in cur.fetchall():
    schema_data["foreign_keys"].append({
        "table": row[0],
        "column": row[1],
        "references_table": row[2],
        "references_column": row[3]
    })

print(f"Found {len(schema_data['foreign_keys'])} foreign keys")

# Get indexes
print("[4/5] Scanning INDEXES...")
cur.execute("""
SELECT 
    indexname,
    tablename,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname
""")

for row in cur.fetchall():
    schema_data["indexes"].append({
        "name": row[0],
        "table": row[1],
        "definition": row[2]
    })

print(f"Found {len(schema_data['indexes'])} indexes")

# Get sequences
print("[5/5] Scanning SEQUENCES...")
cur.execute("""
SELECT sequence_name 
FROM information_schema.sequences 
WHERE sequence_schema = 'public'
ORDER BY sequence_name
""")

for row in cur.fetchall():
    schema_data["sequences"].append(row[0])

print(f"Found {len(schema_data['sequences'])} sequences")

# ============ ANALYSIS ============
print("\n" + "=" * 80)
print("ANALYSIS & ISSUE DETECTION")
print("=" * 80)

# Find duplicate columns across tables
print("\n[Analysis 1] Duplicate Column Names Across Tables...")
column_usage = defaultdict(list)
for table, info in schema_data["tables"].items():
    for col in info["columns"].keys():
        column_usage[col].append(table)

duplicates = {col: tables for col, tables in column_usage.items() if len(tables) > 1}
print(f"Found {len(duplicates)} column names used in multiple tables:")
for col, tables in sorted(duplicates.items()):
    print(f"  '{col}' used in: {', '.join(tables[:5])}" + 
          (f" ... +{len(tables)-5} more" if len(tables) > 5 else ""))
    schema_data["issues"].append({
        "type": "DUPLICATE_COLUMN_NAME",
        "column": col,
        "tables": tables
    })

# Find tables with similar names (potential consolidation)
print("\n[Analysis 2] Similar Table Names (potential consolidation candidates)...")
table_names = sorted(schema_data["tables"].keys())
similar = []
for i, t1 in enumerate(table_names):
    for t2 in table_names[i+1:]:
        # Check if names share significant prefix/suffix
        common = 0
        if t1.replace('_', '').lower() in t2.replace('_', '').lower() or \
           t2.replace('_', '').lower() in t1.replace('_', '').lower():
            similar.append((t1, t2))

if similar:
    for t1, t2 in similar[:10]:
        print(f"  {t1} <-> {t2}")
        schema_data["issues"].append({
            "type": "SIMILAR_TABLE_NAMES",
            "tables": [t1, t2]
        })
else:
    print("  None found")

# Find orphaned tables (no foreign keys)
print("\n[Analysis 3] Tables With No Foreign Key Relationships...")
fk_tables = set(fk["table"] for fk in schema_data["foreign_keys"])
fk_tables.update(set(fk["references_table"] for fk in schema_data["foreign_keys"]))
orphan_tables = set(schema_data["tables"].keys()) - fk_tables
print(f"  {len(orphan_tables)} tables with no FK relationships:")
for t in sorted(orphan_tables):
    row_count = schema_data["tables"][t]["row_count"]
    if row_count == 0:
        print(f"    {t} (EMPTY - potential candidate for removal)")
        schema_data["issues"].append({
            "type": "EMPTY_ORPHAN_TABLE",
            "table": t
        })
    else:
        print(f"    {t} ({row_count} rows)")

# Find tables with NULL columns
print("\n[Analysis 4] Columns That Are Always Nullable...")
always_null = []
for table, info in schema_data["tables"].items():
    for col, col_info in info["columns"].items():
        if col_info["nullable"]:
            # Check if column actually has any non-null data
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NOT NULL")
                count = cur.fetchone()[0]
                if count == 0 and info["row_count"] > 0:
                    always_null.append((table, col))
            except:
                pass

if always_null:
    print(f"  Found {len(always_null)} columns that are always NULL:")
    for table, col in always_null[:10]:
        print(f"    {table}.{col}")
        schema_data["issues"].append({
            "type": "ALWAYS_NULL_COLUMN",
            "table": table,
            "column": col
        })
else:
    print("  None found")

# Check for NULL in primary key
print("\n[Analysis 5] NULL Values in Key Columns...")
for table, info in schema_data["tables"].items():
    for col, col_info in info["columns"].items():
        if any(x in col.lower() for x in ['id', 'key', 'code', 'number']):
            if col_info["nullable"]:
                print(f"  ⚠ {table}.{col} is nullable but looks like a key!")
                schema_data["issues"].append({
                    "type": "NULLABLE_KEY_COLUMN",
                    "table": table,
                    "column": col
                })

cur.close()
conn.close()

# Save comprehensive schema file
output_file = "l:\\limo\\DATABASE_SCHEMA_INVENTORY.json"
with open(output_file, 'w') as f:
    json.dump(schema_data, f, indent=2, default=str)

print(f"\n✅ Saved comprehensive schema to: {output_file}")
print(f"   Total tables: {len(schema_data['tables'])}")
print(f"   Total views: {len(schema_data['views'])}")
print(f"   Total issues found: {len(schema_data['issues'])}")

# Create human-readable markdown report
report_file = "l:\\limo\\DATABASE_SCHEMA_REPORT.md"
with open(report_file, 'w') as f:
    f.write("# Database Schema Audit Report\n\n")
    f.write(f"Generated for: **almsdata** database\n\n")
    f.write(f"## Summary\n")
    f.write(f"- **Tables**: {len(schema_data['tables'])}\n")
    f.write(f"- **Views**: {len(schema_data['views'])}\n")
    f.write(f"- **Foreign Keys**: {len(schema_data['foreign_keys'])}\n")
    f.write(f"- **Indexes**: {len(schema_data['indexes'])}\n")
    f.write(f"- **Sequences**: {len(schema_data['sequences'])}\n")
    f.write(f"- **Issues Found**: {len(schema_data['issues'])}\n\n")
    
    f.write(f"## Issues Detected\n\n")
    
    # Group by issue type
    issues_by_type = defaultdict(list)
    for issue in schema_data["issues"]:
        issues_by_type[issue["type"]].append(issue)
    
    for issue_type, issues in sorted(issues_by_type.items()):
        f.write(f"### {issue_type} ({len(issues)} found)\n\n")
        for issue in issues:
            if issue_type == "DUPLICATE_COLUMN_NAME":
                f.write(f"- **{issue['column']}** in tables: {', '.join(issue['tables'][:5])}\n")
            elif issue_type == "SIMILAR_TABLE_NAMES":
                f.write(f"- {issue['tables'][0]} ↔ {issue['tables'][1]}\n")
            elif issue_type in ("EMPTY_ORPHAN_TABLE", "ALWAYS_NULL_COLUMN", "NULLABLE_KEY_COLUMN"):
                f.write(f"- **{issue.get('table', 'N/A')}.{issue.get('column', 'N/A')}**\n")
        f.write("\n")
    
    f.write(f"\n## Tables By Size\n\n")
    tables_by_size = sorted(schema_data["tables"].items(), 
                           key=lambda x: x[1]["size_mb"], reverse=True)
    for table, info in tables_by_size[:20]:
        f.write(f"- **{table}**: {info['size_mb']:.2f} MB ({info['row_count']:,} rows)\n")

print(f"✅ Saved readable report to: {report_file}")
