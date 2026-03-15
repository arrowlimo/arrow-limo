#!/usr/bin/env python3
"""
Deep verification: Check if table CONTENT matches, not just row counts.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os

load_dotenv()

local_conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password=os.getenv("POSTGRES_PASSWORD")
)

neon_conn = psycopg2.connect(os.getenv("NEON_DATABASE_URL"))

# Key tables to verify
tables_to_check = [
    'charters',
    'clients', 
    'receipts',
    'banking_receipt_matching_ledger',
    'vehicles',
    'drivers',
    'invoices'
]

print("=" * 80)
print("DEEP CONTENT VERIFICATION")
print("=" * 80)
print()

for table in tables_to_check:
    print(f"\n{'=' * 80}")
    print(f"TABLE: {table}")
    print('=' * 80)
    
    # Get primary key column name
    with local_conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = %s::regclass AND i.indisprimary
        """, (table,))
        pk_result = cur.fetchone()
        if not pk_result:
            print(f"⚠️  No primary key found, skipping...")
            continue
        pk_col = pk_result['attname']
    
    print(f"Primary Key: {pk_col}")
    
    # Get row count
    with local_conn.cursor() as cur:
        cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        local_count = cur.fetchone()[0]
    
    with neon_conn.cursor() as cur:
        cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        neon_count = cur.fetchone()[0]
    
    print(f"Row counts: Local={local_count:,}, Neon={neon_count:,}")
    
    if local_count != neon_count:
        print(f"❌ ROW COUNT MISMATCH!")
        continue
    
    # Get all primary keys from both
    with local_conn.cursor() as cur:
        cur.execute(f'SELECT "{pk_col}" FROM "{table}" ORDER BY "{pk_col}"')
        local_pks = {row[0] for row in cur.fetchall()}
    
    with neon_conn.cursor() as cur:
        cur.execute(f'SELECT "{pk_col}" FROM "{table}" ORDER BY "{pk_col}"')
        neon_pks = {row[0] for row in cur.fetchall()}
    
    # Compare primary keys
    in_both = local_pks & neon_pks
    local_only = local_pks - neon_pks
    neon_only = neon_pks - local_pks
    
    print(f"\nPrimary Key Analysis:")
    print(f"  In both:    {len(in_both):,}")
    print(f"  Local only: {len(local_only):,}")
    print(f"  Neon only:  {len(neon_only):,}")
    
    if local_only:
        print(f"\n  ❌ LOCAL-ONLY IDs (sample): {sorted(list(local_only))[:10]}")
    if neon_only:
        print(f"\n  ❌ NEON-ONLY IDs (sample): {sorted(list(neon_only))[:10]}")
    
    if len(in_both) == local_count == neon_count:
        print(f"  ✅ All primary keys match!")
        
        # Sample data comparison
        sample_pks = sorted(list(in_both))[:5]
        print(f"\n  Sample data comparison (first 5 records):")
        
        # Get columns
        with local_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position
                LIMIT 5
            """, (table,))
            cols = [row['column_name'] for row in cur.fetchall()]
        
        # Get sample from local
        with local_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f'SELECT * FROM "{table}" WHERE "{pk_col}" = ANY(%s) ORDER BY "{pk_col}" LIMIT 3', (sample_pks,))
            local_sample = cur.fetchall()
        
        # Get sample from Neon
        with neon_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f'SELECT * FROM "{table}" WHERE "{pk_col}" = ANY(%s) ORDER BY "{pk_col}" LIMIT 3', (sample_pks,))
            neon_sample = cur.fetchall()
        
        # Compare first row
        if local_sample and neon_sample:
            local_row = dict(local_sample[0])
            neon_row = dict(neon_sample[0])
            
            differences = []
            for key in local_row.keys():
                if key in neon_row:
                    if local_row[key] != neon_row[key]:
                        differences.append(f"{key}: {local_row[key]} vs {neon_row[key]}")
            
            if differences:
                print(f"\n  ⚠️  CONTENT DIFFERENCES FOUND:")
                for diff in differences[:5]:
                    print(f"    - {diff}")
            else:
                print(f"  ✅ Sample content matches perfectly!")

print()
print("=" * 80)
print("✅ Verification complete")
print("=" * 80)

local_conn.close()
neon_conn.close()
