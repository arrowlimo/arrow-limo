#!/usr/bin/env python
"""Expand vehicle_type column by temporarily dropping dependent view."""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

print("\n" + "=" * 100)
print("EXPANDING VEHICLE_TYPE COLUMN")
print("=" * 100)

# Find dependent views
cur.execute("""
    SELECT DISTINCT v.view_name
    FROM information_schema.view_column_usage v
    WHERE v.table_name = 'vehicles'
    AND v.column_name = 'vehicle_type'
""")

views = [row[0] for row in cur.fetchall()]
print(f"\nFound {len(views)} dependent views: {', '.join(views) if views else 'None'}")

# Store view definitions
view_defs = {}
for view_name in views:
    cur.execute(f"SELECT pg_get_viewdef('{view_name}'::regclass, true)")
    view_defs[view_name] = cur.fetchone()[0]
    print(f"  Stored definition for: {view_name}")

# Drop views
for view_name in views:
    print(f"  Dropping view: {view_name}")
    cur.execute(f"DROP VIEW IF EXISTS {view_name} CASCADE")

# Alter column
print("\n" + "=" * 100)
print("Altering vehicle_type column VARCHAR(20) → VARCHAR(100)")
cur.execute("ALTER TABLE vehicles ALTER COLUMN vehicle_type TYPE VARCHAR(100)")
print("✅ Column expanded successfully")

# Recreate views
print("\n" + "=" * 100)
print("Recreating views:")
for view_name, view_def in view_defs.items():
    print(f"  Recreating: {view_name}")
    cur.execute(f"CREATE OR REPLACE VIEW {view_name} AS {view_def}")

conn.commit()

print("\n" + "=" * 100)
print("✅ COMPLETE - vehicle_type is now VARCHAR(100)")
print("=" * 100)

cur.close()
conn.close()
