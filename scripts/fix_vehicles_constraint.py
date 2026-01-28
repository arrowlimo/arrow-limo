#!/usr/bin/env python
"""Drop incorrect unique constraint on vehicles.vehicle_type."""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print("\n" + "=" * 100)
print("CHECKING UNIQUE CONSTRAINT ON VEHICLES")
print("=" * 100)

# Check for unique constraints
cur.execute("""
    SELECT conname, contype, pg_get_constraintdef(oid)
    FROM pg_constraint
    WHERE conrelid = 'vehicles'::regclass
""")

constraints = cur.fetchall()
print("\nCurrent constraints on vehicles table:")
print("-" * 100)
for name, ctype, definition in constraints:
    constraint_type = {'p': 'PRIMARY KEY', 'u': 'UNIQUE', 'f': 'FOREIGN KEY', 'c': 'CHECK'}.get(ctype, ctype)
    print(f"{name:<40} {constraint_type:<15} {definition}")

# Drop the incorrect unique constraint
print("\n" + "=" * 100)
print("DROPPING INCORRECT UNIQUE CONSTRAINT")
print("=" * 100)

try:
    cur.execute("DROP INDEX IF EXISTS idx_vehicles_code CASCADE")
    conn.commit()
    print("\n✅ Dropped idx_vehicles_code constraint")
except Exception as e:
    print(f"\n⚠️  Error dropping constraint: {e}")
    conn.rollback()

# Verify
cur.execute("""
    SELECT conname, contype, pg_get_constraintdef(oid)
    FROM pg_constraint
    WHERE conrelid = 'vehicles'::regclass
""")

print("\nRemaining constraints on vehicles table:")
print("-" * 100)
for name, ctype, definition in cur.fetchall():
    constraint_type = {'p': 'PRIMARY KEY', 'u': 'UNIQUE', 'f': 'FOREIGN KEY', 'c': 'CHECK'}.get(ctype, ctype)
    print(f"{name:<40} {constraint_type:<15} {definition}")

cur.close()
conn.close()

print("\n" + "=" * 100)
print("✅ COMPLETE - You can now reclassify vehicles")
print("=" * 100)
