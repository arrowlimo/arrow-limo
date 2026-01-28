#!/usr/bin/env python3
"""
Execute clients name standardization migration
"""
import os
import psycopg2
from pathlib import Path

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Read migration file
    migration_file = Path("migrations/20260124_clients_name_standardization.sql")
    with open(migration_file, 'r') as f:
        sql = f.read()
    
    # Execute migration
    print("🔄 Executing migration: clients_name_standardization...")
    cur.execute(sql)
    conn.commit()
    
    print("✅ Migration completed successfully!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    if conn:
        conn.rollback()
        conn.close()
    exit(1)
finally:
    if cur:
        cur.close()
    if conn:
        conn.close()
