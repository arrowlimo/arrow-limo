#!/usr/bin/env python3
"""Diagnose Neon schema to see why restore failed partially."""
import psycopg2

neon_conn = psycopg2.connect(
    host="ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech",
    user="neondb_owner",
    password="***REMOVED***",
    database="neondb",
    sslmode="require"
)

ncur = neon_conn.cursor()

# Check if payments table exists
ncur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='payments')")
payments_exists = ncur.fetchone()[0]

# Check if receipts table exists
ncur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='receipts')")
receipts_exists = ncur.fetchone()[0]

print(f"✓ Payments table exists: {payments_exists}")
print(f"✓ Receipts table exists: {receipts_exists}")

# Get all tables
ncur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
tables = [r[0] for r in ncur.fetchall()]

print(f"\nTotal tables in Neon: {len(tables)}")
print("Tables by category:")

core_tables = ['charters', 'payments', 'receipts', 'charter_charges', 'employees', 'vehicles']
for t in core_tables:
    if t in tables:
        ncur.execute(f"SELECT COUNT(*) FROM {t}")
        count = ncur.fetchone()[0]
        print(f"  ✓ {t:<25} {count:>10,} rows")
    else:
        print(f"  ✗ {t:<25} MISSING")

ncur.close()
neon_conn.close()
