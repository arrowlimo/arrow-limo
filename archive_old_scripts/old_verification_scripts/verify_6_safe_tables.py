#!/usr/bin/env python3
"""Quick verification that 6 safe tables synced correctly."""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Connect to both databases
local = psycopg2.connect(
    host='localhost',
    database=os.getenv('LOCAL_DB_NAME'),
    user=os.getenv('LOCAL_DB_USER'),
    password=os.getenv('LOCAL_DB_PASSWORD')
)

neon = psycopg2.connect(
    host=os.getenv('NEON_DB_HOST'),
    database=os.getenv('NEON_DB_NAME'),
    user=os.getenv('NEON_DB_USER'),
    password=os.getenv('NEON_DB_PASSWORD'),
    sslmode='require'
)

tables = [
    'beverage_products',
    'lms2026_payment_matches',
    'charter_gst_details_2010_2012',
    'employee_t4_records',
    'employee_t4_summary',
    'alcohol_business_tracking'
]

print("\n" + "="*80)
print("6 SAFE TABLES - SYNC VERIFICATION")
print("="*80)

all_match = True
total_rows = 0

for table in tables:
    local_cur = local.cursor()
    local_cur.execute(f'SELECT COUNT(*) FROM "{table}"')
    local_count = local_cur.fetchone()[0]
    local_cur.close()
    
    neon_cur = neon.cursor()
    neon_cur.execute(f'SELECT COUNT(*) FROM "{table}"')
    neon_count = neon_cur.fetchone()[0]
    neon_cur.close()
    
    match = "✅ MATCH" if local_count == neon_count else "❌ MISMATCH"
    if local_count != neon_count:
        all_match = False
    
    total_rows += neon_count
    
    print(f"{table:40} Local: {local_count:>8,} | Neon: {neon_count:>8,} | {match}")

print("="*80)
print(f"Total rows synced: {total_rows:,}")

if all_match:
    print("\n✅ ALL 6 TABLES SYNCED SUCCESSFULLY - NO ERRORS")
else:
    print("\n❌ SOME TABLES HAVE MISMATCHES - ERRORS DETECTED")

local.close()
neon.close()
