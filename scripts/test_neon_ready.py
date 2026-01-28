#!/usr/bin/env python3
"""
Quick test: Verify Neon database has data and is accessible
"""
import os
import psycopg2

NEON_CONFIG = {
    "host": "ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech",
    "port": 5432,
    "database": "neondb",
    "user": "neondb_owner",
    "password": "***REMOVED***",
    "sslmode": "require",
}

print("="*80)
print("NEON DATABASE - Connection Test")
print("="*80)

try:
    print(f"\nConnecting to: {NEON_CONFIG['host']}")
    conn = psycopg2.connect(**NEON_CONFIG)
    cur = conn.cursor()
    
    print("✅ Connected successfully\n")
    
    # Check key tables
    tables = [
        ("charters", "SELECT COUNT(*) FROM charters"),
        ("payments", "SELECT COUNT(*) FROM payments"),
        ("clients", "SELECT COUNT(*) FROM clients"),
        ("employees", "SELECT COUNT(*) FROM employees"),
        ("vehicles", "SELECT COUNT(*) FROM vehicles"),
        ("receipts", "SELECT COUNT(*) FROM receipts"),
    ]
    
    print("Table counts:")
    for table_name, query in tables:
        try:
            cur.execute(query)
            count = cur.fetchone()[0]
            print(f"  ✅ {table_name}: {count:,}")
        except Exception as e:
            print(f"  ❌ {table_name}: Error - {e}")
    
    # Check sample charter
    print("\nSample charter test:")
    cur.execute("""
        SELECT reserve_number, charter_date, total_amount_due, paid_amount, balance
        FROM charters
        ORDER BY charter_date DESC
        LIMIT 3
    """)
    rows = cur.fetchall()
    if rows:
        print("  Recent charters:")
        for row in rows:
            print(f"    Reserve: {row[0]} | Date: {row[1]} | Due: ${row[2]} | Paid: ${row[3]} | Balance: ${row[4]}")
    else:
        print("  ⚠️  No charters found")
    
    # Check if cvip columns exist (verify schema updates)
    print("\nSchema verification (CVIP columns):")
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='vehicles' 
        AND column_name IN ('cvip_inspection_number', 'cvip_expiry_date', 'last_cvip_date')
        ORDER BY column_name
    """)
    cvip_cols = [r[0] for r in cur.fetchall()]
    if len(cvip_cols) == 3:
        print(f"  ✅ CVIP columns present: {', '.join(cvip_cols)}")
    else:
        print(f"  ⚠️  CVIP columns: {cvip_cols} (expected 3)")
    
    # Check if deprecated columns are gone
    print("\nDeprecated column check:")
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='employees' 
        AND column_name IN ('cvip_expiry', 'driver_code')
    """)
    deprecated = [r[0] for r in cur.fetchall()]
    if deprecated:
        print(f"  ⚠️  Deprecated columns still present: {deprecated}")
    else:
        print(f"  ✅ Deprecated columns removed")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*80)
    print("✅ NEON DATABASE READY")
    print("="*80)
    print("\nNeon is ready for use as master database")
    print("Run desktop app: python desktop_app/main.py")
    print("  → Choose 'Neon (master - online)' at startup")
    
except Exception as e:
    print(f"\n❌ Connection failed: {e}")
    print("\nNeon may need to be restored from local backup.")
    print("Run: scripts/restore_local_to_neon.ps1")
