#!/usr/bin/env python3
"""Verify FK constraints now work in Neon with vehicles restored."""
import psycopg2

NEON_CONN = "dbname=neondb host=ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech user=neondb_owner password=npg_89MbcFmZwUWo sslmode=require"

try:
    conn = psycopg2.connect(NEON_CONN)
    cur = conn.cursor()
    
    print("Verifying FK constraints...\n")
    
    # Check if any charters reference non-existent vehicles
    cur.execute("""
        SELECT COUNT(*) as orphaned_charters
        FROM charters c
        WHERE c.vehicle_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM vehicles v WHERE v.vehicle_id = c.vehicle_id)
    """)
    orphaned = cur.fetchone()[0]
    print(f"Charters with missing vehicles: {orphaned}")
    
    # Check if any receipts reference non-existent vehicles
    cur.execute("""
        SELECT COUNT(*) as orphaned_receipts
        FROM receipts r
        WHERE r.vehicle_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM vehicles v WHERE v.vehicle_id = r.vehicle_id)
    """)
    orphaned_receipts = cur.fetchone()[0]
    print(f"Receipts with missing vehicles: {orphaned_receipts}")
    
    # Check sample charter with vehicle
    cur.execute("""
        SELECT c.charter_id, c.reserve_number, c.vehicle_id, v.vehicle_number, v.make, v.model
        FROM charters c
        LEFT JOIN vehicles v ON v.vehicle_id = c.vehicle_id
        WHERE c.vehicle_id IS NOT NULL
        LIMIT 3
    """)
    print(f"\nSample charters with vehicles:")
    for row in cur.fetchall():
        print(f"  Reserve {row[1]}: vehicle_id={row[2]} ({row[3]} {row[4]} {row[5]})")
    
    if orphaned == 0 and orphaned_receipts == 0:
        print("\n✅ SUCCESS: All FK constraints intact!")
    else:
        print(f"\n⚠️  Warning: {orphaned + orphaned_receipts} orphaned rows found")
    
    cur.close()
    conn.close()

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
