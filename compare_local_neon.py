#!/usr/bin/env python3
"""
Compare local almsdata vs Neon to find missing/dropped tables
"""
import psycopg2

NEON_CONN = {
    'host': 'ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech',
    'user': 'neondb_owner',
    'password': '***REMOVED***',
    'database': 'neondb',
    'sslmode': 'require',
}

LOCAL_CONN = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***',
}

print("Comparing local vs Neon schema...\n")

try:
    # Get Neon tables
    neon_conn = psycopg2.connect(**NEON_CONN)
    neon_cur = neon_conn.cursor()
    
    neon_cur.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema='public'
        ORDER BY table_name
    """)
    neon_tables = {r[0] for r in neon_cur.fetchall()}
    
    neon_cur.close()
    neon_conn.close()
    
    # Get local tables
    local_conn = psycopg2.connect(**LOCAL_CONN)
    local_cur = local_conn.cursor()
    
    local_cur.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema='public'
        ORDER BY table_name
    """)
    local_tables = {r[0] for r in local_cur.fetchall()}
    
    local_cur.close()
    local_conn.close()
    
    # Compare
    print(f"Total tables in Neon:  {len(neon_tables)}")
    print(f"Total tables in local: {len(local_tables)}")
    print()
    
    # Tables in Neon but NOT in local (MISSING)
    missing = neon_tables - local_tables
    if missing:
        print(f"⚠️  MISSING in local ({len(missing)} tables):")
        for table in sorted(missing):
            print(f"   - {table}")
    else:
        print("✅ No missing tables (all Neon tables present in local)")
    
    # Tables in local but NOT in Neon (NEW)
    new = local_tables - neon_tables
    if new:
        print(f"\n🆕 NEW in local ({len(new)} tables) - from our migrations:")
        for table in sorted(new):
            print(f"   - {table}")
    else:
        print("\n✅ No new tables")
    
    print()
    
    # Check row counts for large tables that might have data loss
    large_tables = [
        'charters', 'payments', 'receipts', 'banking_transactions',
        'employees', 'vehicles', 'clients',
        'qb_export_invoices', 'invoice_tracking'
    ]
    
    print("Row count comparison for key tables:")
    neon_conn = psycopg2.connect(**NEON_CONN)
    neon_cur = neon_conn.cursor()
    
    local_conn = psycopg2.connect(**LOCAL_CONN)
    local_cur = local_conn.cursor()
    
    for table in large_tables:
        try:
            neon_cur.execute(f"SELECT COUNT(*) FROM {table}")
            neon_count = neon_cur.fetchone()[0]
        except:
            neon_count = "N/A"
        
        try:
            local_cur.execute(f"SELECT COUNT(*) FROM {table}")
            local_count = local_cur.fetchone()[0]
        except:
            local_count = "N/A"
        
        # Mark as warning if counts differ
        if neon_count != "N/A" and local_count != "N/A":
            status = "✅" if neon_count == local_count else "⚠️"
            print(f"  {status} {table:<30} Neon: {neon_count:>8} | Local: {local_count:>8}")
        else:
            print(f"  ❓ {table:<30} Neon: {neon_count:>8} | Local: {local_count:>8}")
    
    neon_cur.close()
    neon_conn.close()
    local_cur.close()
    local_conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
