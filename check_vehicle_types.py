#!/usr/bin/env python3
"""Check vehicle types in both tables"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 60)
print("VEHICLE TYPES IN vehicle_pricing_defaults:")
print("=" * 60)
cur.execute("""
    SELECT vehicle_type FROM vehicle_pricing_defaults 
    WHERE vehicle_type IS NOT NULL AND vehicle_type != '' 
    ORDER BY vehicle_type
""")
pricing_types = [row[0] for row in cur.fetchall()]
for vt in pricing_types:
    print(f"  ✓ {vt}")

print("\n" + "=" * 60)
print("VEHICLE TYPES IN vehicles TABLE (fallback):")
print("=" * 60)
cur.execute("""
    SELECT DISTINCT vehicle_type FROM vehicles 
    WHERE vehicle_type IS NOT NULL AND vehicle_type != '' 
    ORDER BY vehicle_type
""")
vehicle_types = [row[0] for row in cur.fetchall()]
for vt in vehicle_types:
    status = "✓" if vt in pricing_types else "⚠ (not in pricing_defaults)"
    print(f"  {status} {vt}")

print("\n" + "=" * 60)
print("FINAL MERGED LIST (for dropdown):")
print("=" * 60)
merged = pricing_types.copy()
for vt in vehicle_types:
    if vt not in merged:
        merged.append(vt)
merged = sorted(set(merged))
for i, vt in enumerate(merged, 1):
    print(f"  {i:2}. {vt}")

cur.close()
conn.close()
print(f"\nTotal: {len(merged)} types")
