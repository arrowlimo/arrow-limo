#!/usr/bin/env python3
"""
Identify next table with discrepancies between local and Neon.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os

load_dotenv()

local_conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password=os.getenv("POSTGRES_PASSWORD")
)

neon_conn = psycopg2.connect(os.getenv("NEON_DATABASE_URL"))

print("=" * 80)
print("TABLE COMPARISON: LOCAL vs NEON")
print("=" * 80)
print()

# Get all tables from local
print("Loading table list from local database...")
with local_conn.cursor(cursor_factory=RealDictCursor) as cur:
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    local_tables = {row['table_name'] for row in cur.fetchall()}
    print(f"✅ Local: {len(local_tables)} tables")

# Get all tables from Neon
print("Loading table list from Neon database...")
with neon_conn.cursor(cursor_factory=RealDictCursor) as cur:
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    neon_tables = {row['table_name'] for row in cur.fetchall()}
    print(f"✅ Neon: {len(neon_tables)} tables")

# Find tables in both
common_tables = local_tables & neon_tables
local_only_tables = local_tables - neon_tables
neon_only_tables = neon_tables - local_tables

print()
print(f"📊 Common tables: {len(common_tables)}")
print(f"📤 Local only: {len(local_only_tables)}")
print(f"📥 Neon only: {len(neon_only_tables)}")

if local_only_tables:
    print(f"\n❌ Tables only in LOCAL: {sorted(local_only_tables)}")
if neon_only_tables:
    print(f"\n❌ Tables only in NEON: {sorted(neon_only_tables)}")

# Compare row counts for common tables
print()
print("=" * 80)
print("ROW COUNT COMPARISON")
print("=" * 80)
print()

discrepancies = []

for table in sorted(common_tables):
    # Skip certain tables
    if table.startswith('pg_') or table.startswith('sql_'):
        continue
    
    # Get local count
    try:
        with local_conn.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            local_count = cur.fetchone()[0]
    except Exception as e:
        print(f"⚠️  Error counting local {table}: {e}")
        continue
    
    # Get Neon count
    try:
        with neon_conn.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            neon_count = cur.fetchone()[0]
    except Exception as e:
        print(f"⚠️  Error counting Neon {table}: {e}")
        continue
    
    diff = local_count - neon_count
    
    if diff != 0:
        discrepancies.append({
            'table': table,
            'local': local_count,
            'neon': neon_count,
            'diff': diff,
            'diff_abs': abs(diff)
        })

# Sort by absolute difference (biggest problems first)
discrepancies.sort(key=lambda x: x['diff_abs'], reverse=True)

if discrepancies:
    print(f"{'Table':<40} {'Local':>10} {'Neon':>10} {'Difference':>12}")
    print("-" * 80)
    for d in discrepancies:
        sign = "+" if d['diff'] > 0 else ""
        print(f"{d['table']:<40} {d['local']:>10,} {d['neon']:>10,} {sign}{d['diff']:>11,}")
    
    print()
    print("=" * 80)
    print("TOP 5 SUSPECT TABLES (by discrepancy size)")
    print("=" * 80)
    for i, d in enumerate(discrepancies[:5], 1):
        print(f"\n{i}. {d['table']}")
        print(f"   Local: {d['local']:,} rows")
        print(f"   Neon:  {d['neon']:,} rows")
        print(f"   Diff:  {d['diff']:+,} rows")
else:
    print("✅ All tables have matching row counts!")

print()
print("=" * 80)
print("✅ Analysis complete")
print("=" * 80)

local_conn.close()
neon_conn.close()
