#!/usr/bin/env python3
"""List all staging tables in the database."""
import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

# Get staging tables with row counts
cur.execute("""
    SELECT 
        table_name,
        (SELECT COUNT(*) 
         FROM information_schema.columns c 
         WHERE c.table_name = t.table_name) as col_count
    FROM information_schema.tables t
    WHERE table_schema = 'public'
    AND table_name LIKE '%staging%'
    ORDER BY table_name
""")

staging_tables = cur.fetchall()

print("\n" + "=" * 80)
print("STAGING TABLES IN DATABASE")
print("=" * 80)
print(f"\n{'Table Name':<50} {'Columns':<10}")
print("-" * 65)

for table_name, col_count in staging_tables:
    # Get row count for each table
    try:
        cur.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        row_count = cur.fetchone()[0]
        print(f"{table_name:<50} {col_count:<10} {row_count:>10,} rows")
    except Exception as e:
        print(f"{table_name:<50} {col_count:<10} {'ERROR':>10}")

print("\n" + "=" * 80)
print(f"Total staging tables found: {len(staging_tables)}")
print("=" * 80 + "\n")

cur.close()
conn.close()
