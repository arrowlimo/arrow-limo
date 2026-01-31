#!/usr/bin/env python3
import psycopg2

LOCAL_CONN = "dbname=almsdata host=localhost user=postgres password=***REDACTED***"
NEON_CONN = "dbname=neondb host=ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech user=neondb_owner password=npg_89MbcFmZwUWo sslmode=require"

# Get local columns
local_conn = psycopg2.connect(LOCAL_CONN)
local_cur = local_conn.cursor()
local_cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name='vehicles' 
    ORDER BY ordinal_position
""")
local_cols = set(row[0] for row in local_cur.fetchall())
local_cur.close()
local_conn.close()

# Get Neon columns
neon_conn = psycopg2.connect(NEON_CONN)
neon_cur = neon_conn.cursor()
neon_cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name='vehicles' 
    ORDER BY ordinal_position
""")
neon_cols = set(row[0] for row in neon_cur.fetchall())
neon_cur.close()
neon_conn.close()

print(f"Local columns: {len(local_cols)}")
print(f"Neon columns: {len(neon_cols)}\n")

# Differences
in_local_not_neon = local_cols - neon_cols
in_neon_not_local = neon_cols - local_cols

if in_local_not_neon:
    print(f"❌ In LOCAL but not in NEON ({len(in_local_not_neon)}):")
    for col in sorted(in_local_not_neon):
        print(f"   - {col}")

if in_neon_not_local:
    print(f"\n❌ In NEON but not in LOCAL ({len(in_neon_not_local)}):")
    for col in sorted(in_neon_not_local):
        print(f"   + {col}")

if not in_local_not_neon and not in_neon_not_local:
    print("✅ Columns match!")
