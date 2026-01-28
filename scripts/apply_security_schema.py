#!/usr/bin/env python3
"""Apply security schema to database."""

import os
import sys
import psycopg2

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
    cursor = conn.cursor()
    
    # Read and execute schema
    with open('sql/security_multiuser_schema.sql', 'r') as f:
        schema = f.read()
    
    # Execute statements
    cursor.execute(schema)
    conn.commit()
    
    print("✅ Security schema applied successfully")
    
    # Verify tables created
    cursor.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name IN (
            'password_reset_tokens', 'concurrent_edits', 'record_locks', 'staged_edits', 'audit_log'
        )
        ORDER BY table_name
    """)
    
    tables = [row[0] for row in cursor.fetchall()]
    print(f"\n📋 Created tables ({len(tables)}):")
    for table in tables:
        print(f"   • {table}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
