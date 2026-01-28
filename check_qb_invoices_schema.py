#!/usr/bin/env python3
"""
Check exact column names in qb_export_invoices on Neon
"""
import psycopg2

NEON_CONN = {
    'host': 'ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech',
    'user': 'neondb_owner',
    'password': '***REMOVED***',
    'database': 'neondb',
    'sslmode': 'require',
}

print("Checking qb_export_invoices schema on Neon...\n")

try:
    conn = psycopg2.connect(**NEON_CONN)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'qb_export_invoices'
        ORDER BY ordinal_position
    """)
    
    columns = cur.fetchall()
    print(f"Columns in qb_export_invoices:")
    for col_name, col_type, nullable in columns:
        print(f"  - {col_name:<30} {col_type:<20} {nullable}")
    
    # Try to get one row
    cur.execute("SELECT * FROM qb_export_invoices LIMIT 1")
    row = cur.fetchone()
    if row:
        print(f"\nSample row:")
        for col_name, value in zip([c[0] for c in columns], row):
            print(f"  {col_name}: {value}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
