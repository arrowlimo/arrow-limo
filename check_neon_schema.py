#!/usr/bin/env python3
"""
Check Neon schema for invoices-related tables
"""
import psycopg2

NEON_CONN = {
    'host': 'ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech',
    'user': 'neondb_owner',
    'password': '***REMOVED***',
    'database': 'neondb',
    'sslmode': 'require',
}

print("Neon database schema for invoices-related tables...\n")

try:
    conn = psycopg2.connect(**NEON_CONN)
    cur = conn.cursor()
    
    # List all tables
    cur.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema='public' AND table_name LIKE '%invoice%'
        ORDER BY table_name
    """)
    
    tables = [r[0] for r in cur.fetchall()]
    
    if not tables:
        print("❌ No invoice-related tables found in Neon")
    else:
        print(f"✅ Found {len(tables)} invoice-related table(s):")
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"   - {table}: {count} rows")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
