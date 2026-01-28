#!/usr/bin/env python
import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

try:
    # Remove specific vehicle types
    to_remove = [
        'Bus (30 pax)',
        'Bus (72 pax)',
        'Shuttle Bus (16 pax)'
    ]
    
    print("🗑️ Removing vehicle types:")
    for vtype in to_remove:
        cur.execute("DELETE FROM vehicle_pricing_defaults WHERE vehicle_type = %s", (vtype,))
        print(f"  ✅ Removed: {vtype}")
    
    conn.commit()
    
    # Show remaining
    cur.execute("SELECT vehicle_type, nrr FROM vehicle_pricing_defaults ORDER BY vehicle_type")
    remaining = cur.fetchall()
    print(f"\n📊 Remaining {len(remaining)} vehicle types:")
    for vtype, nrr in remaining:
        print(f"  - {vtype}: NRR=${nrr}")
    
except Exception as e:
    conn.rollback()
    print(f"❌ Error: {e}")
finally:
    conn.close()
