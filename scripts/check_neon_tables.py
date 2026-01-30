#!/usr/bin/env python3
import psycopg2

print("Checking Neon database state after restore...")
try:
    conn = psycopg2.connect(
        host='ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech',
        database='neondb',
        user='neondb_owner',
        password='npg_89MbcFmZwUWo',
        sslmode='require'
    )
    cur = conn.cursor()
    
    # Check tables
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_schema='public'
    """)
    table_count = cur.fetchone()[0]
    print(f"Total tables: {table_count:,}")
    
    # Check key tables
    tables = ['charters', 'payments', 'vehicles', 'employees', 'clients', 'receipts']
    for table in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"  {table}: {count:,}")
        except Exception as e:
            print(f"  {table}: ERROR - {str(e)[:50]}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
