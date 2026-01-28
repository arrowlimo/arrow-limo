#!/usr/bin/env python3
"""
Query the Neon database to check if invoices table exists and has data
"""
import psycopg2
import sys

NEON_CONN = {
    'host': 'ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech',
    'user': 'neondb_owner',
    'password': '***REMOVED***',
    'database': 'neondb',
    'sslmode': 'require',
}

print("Attempting to connect to Neon...")

try:
    conn = psycopg2.connect(**NEON_CONN)
    print("✅ Connected to Neon database")
    
    cur = conn.cursor()
    
    # Check if invoices table exists
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name='invoices'
        )
    """)
    
    invoices_exists = cur.fetchone()[0]
    
    if invoices_exists:
        print("\n✅ invoices table EXISTS in Neon")
        
        # Count rows
        cur.execute("SELECT COUNT(*) FROM invoices")
        row_count = cur.fetchone()[0]
        print(f"   Row count: {row_count}")
        
        # Get column names
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name='invoices' 
            ORDER BY ordinal_position
        """)
        columns = [r[0] for r in cur.fetchall()]
        print(f"   Columns: {columns[:10]}...")
        
        # If has data, show sample
        if row_count > 0:
            cur.execute("SELECT * FROM invoices LIMIT 1")
            sample = cur.fetchone()
            print(f"\n   Sample row (first row):")
            for i, col in enumerate(columns[:5]):
                print(f"     {col}: {sample[i] if i < len(sample) else 'NULL'}")
    else:
        print("\n❌ invoices table DOES NOT exist in Neon")
    
    # Also check invoice_line_items
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name='invoice_line_items'
        )
    """)
    line_items_exists = cur.fetchone()[0]
    
    if line_items_exists:
        cur.execute("SELECT COUNT(*) FROM invoice_line_items")
        count = cur.fetchone()[0]
        print(f"\n✅ invoice_line_items table EXISTS in Neon ({count} rows)")
    else:
        print(f"\n❌ invoice_line_items table DOES NOT exist in Neon")
    
    cur.close()
    conn.close()
    
except psycopg2.Error as e:
    print(f"❌ Failed to connect to Neon: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
