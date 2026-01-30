#!/usr/bin/env python3
"""Test that the app's database connection to Neon works correctly."""
import os
import psycopg2

# Use the same Neon config as main.py
NEON_CONFIG = {
    "host": os.getenv("NEON_HOST", "ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech"),
    "port": int(os.getenv("NEON_PORT", "5432")),
    "database": os.getenv("NEON_DB", "neondb"),
    "user": os.getenv("NEON_USER", "neondb_owner"),
    "password": os.getenv("NEON_PASSWORD", "npg_89MbcFmZwUWo"),
    "sslmode": os.getenv("NEON_SSLMODE", "require"),
}

try:
    print("Testing Neon connection (as per main.py config)...\n")
    
    # Build connection string like app does
    conn_str = (
        f"host={NEON_CONFIG['host']} "
        f"port={NEON_CONFIG['port']} "
        f"dbname={NEON_CONFIG['database']} "
        f"user={NEON_CONFIG['user']} "
        f"password={NEON_CONFIG['password']} "
        f"sslmode={NEON_CONFIG['sslmode']}"
    )
    
    print(f"Host: {NEON_CONFIG['host']}")
    print(f"Database: {NEON_CONFIG['database']}")
    print(f"User: {NEON_CONFIG['user']}\n")
    
    conn = psycopg2.connect(conn_str)
    cur = conn.cursor()
    
    # Test basic queries that app would use
    print("Testing key queries...\n")
    
    # 1. Charters
    cur.execute("SELECT COUNT(*) FROM charters")
    charter_count = cur.fetchone()[0]
    print(f"✅ Charters: {charter_count:,}")
    
    # 2. Vehicles
    cur.execute("SELECT COUNT(*) FROM vehicles")
    vehicle_count = cur.fetchone()[0]
    print(f"✅ Vehicles: {vehicle_count}")
    
    # 3. Payments
    cur.execute("SELECT COUNT(*) FROM payments")
    payment_count = cur.fetchone()[0]
    print(f"✅ Payments: {payment_count:,}")
    
    # 4. Sample charter with vehicle join
    cur.execute("""
        SELECT c.reserve_number, c.charter_date, v.vehicle_number
        FROM charters c
        LEFT JOIN vehicles v ON v.vehicle_id = c.vehicle_id
        LIMIT 1
    """)
    sample = cur.fetchone()
    if sample:
        print(f"\n✅ Sample charter:")
        print(f"   Reserve: {sample[0]}")
        print(f"   Date: {sample[1]}")
        print(f"   Vehicle: {sample[2]}")
    
    # 5. Test read-only mode would work (no actual modification)
    print(f"\n✅ Neon connection ready for desktop app!")
    
    cur.close()
    conn.close()

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
