#!/usr/bin/env python3
"""Apply charter_routes table migration."""

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

# Read migration file
with open(r"l:\limo\migrations\2025-12-10_create_charter_routes_table.sql", "r", encoding="utf-8") as f:
    migration_sql = f.read()

# Connect and execute
conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

try:
    print("Applying charter_routes table migration...")
    cur.execute(migration_sql)
    conn.commit()
    print("✓ Migration applied successfully")
    
    # Verify table creation
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'charter_routes' 
        ORDER BY ordinal_position
    """)
    
    print("\nCHARTER_ROUTES TABLE COLUMNS:")
    for row in cur.fetchall():
        print(f"  {row[0]:35s} {row[1]}")
        
except Exception as e:
    conn.rollback()
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    cur.close()
    conn.close()
