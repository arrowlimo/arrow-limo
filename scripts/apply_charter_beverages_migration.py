#!/usr/bin/env python3
"""Apply charter_beverages migration"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Read migration file
    with open(r'L:\limo\migrations\2026-01-08_create_charter_beverages.sql', 'r') as f:
        sql = f.read()
    
    # Execute migration
    cur.execute(sql)
    conn.commit()
    
    print("✅ Migration applied successfully!")
    print("✓ Created charter_beverages table")
    print("✓ Created indexes")
    print("✓ Added comments")
    
    # Verify table exists
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'charter_beverages'
        ORDER BY ordinal_position
    """)
    
    print("\nTable structure:")
    print("─" * 50)
    for col_name, data_type in cur.fetchall():
        print(f"  {col_name:<25} {data_type}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Migration failed: {e}")
    if conn:
        conn.rollback()
