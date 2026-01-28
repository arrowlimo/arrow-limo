#!/usr/bin/env python3
"""
Check LOCAL almsdata for QB invoices tables
"""
import psycopg2
import os

LOCAL_CONN = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***',
}

print("Local almsdata schema for QB invoices tables...\n")

try:
    conn = psycopg2.connect(**LOCAL_CONN)
    cur = conn.cursor()
    
    # List all tables matching invoice patterns
    cur.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema='public' AND table_name LIKE '%invoice%'
        ORDER BY table_name
    """)
    
    tables = [r[0] for r in cur.fetchall()]
    
    if not tables:
        print("❌ No invoice-related tables found in local almsdata")
    else:
        print(f"✅ Found {len(tables)} invoice-related table(s) in local:")
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            
            # Get columns
            cur.execute(f"""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name='{table}' 
                ORDER BY ordinal_position
            """)
            cols = [r[0] for r in cur.fetchall()]
            
            print(f"\n   📋 {table}: {count} rows")
            print(f"      Columns ({len(cols)}): {cols[:5]}...")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
