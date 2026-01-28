#!/usr/bin/env python3
"""
Fix name column consistency:
- For individuals (corporate_parent_id=0 with first_name/last_name):
  Reconstruct company_name as "Last, First"
- For companies (no-comma names):
  Keep as is
"""
import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("FIX NAME COLUMN CONSISTENCY")
    print("=" * 80)
    
    # Check current state
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE corporate_parent_id = 0 AND first_name IS NOT NULL) as has_parts,
            COUNT(*) FILTER (WHERE corporate_parent_id = 0 AND first_name IS NOT NULL 
                             AND company_name != CONCAT(last_name, ', ', first_name)) as needs_fix
        FROM clients;
    """)
    
    has_parts, needs_fix = cur.fetchone()
    print(f"\nIndividuals with first_name populated:     {has_parts}")
    print(f"Individuals needing company_name fix:      {needs_fix}")
    
    # Show samples
    print("\n" + "=" * 80)
    print("SAMPLES: Records that need name fixing")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            client_id, 
            company_name as current_name, 
            CONCAT(last_name, ', ', first_name) as should_be
        FROM clients
        WHERE corporate_parent_id = 0 
          AND first_name IS NOT NULL
          AND company_name != CONCAT(last_name, ', ', first_name)
        ORDER BY client_id
        LIMIT 20
    """)
    
    samples = cur.fetchall()
    print(f"\nFirst 20 samples:")
    for client_id, current, should_be in samples:
        print(f"  ID {client_id}: '{current}' → '{should_be}'")
    
    # Confirm
    print("\n" + "=" * 80)
    response = input(f"\nFix all {needs_fix} individual names to 'Last, First' format? [y/N]: ").strip().lower()
    
    if response == 'y':
        print("🔄 Fixing names...")
        
        cur.execute("""
            UPDATE clients
            SET company_name = CONCAT(last_name, ', ', first_name)
            WHERE corporate_parent_id = 0 
              AND first_name IS NOT NULL
              AND company_name != CONCAT(last_name, ', ', first_name);
        """)
        
        conn.commit()
        print(f"✅ Fixed {cur.rowcount} individual names")
    else:
        print("❌ Cancelled")
        conn.close()
        exit(0)
    
    # Verification
    print("\n" + "=" * 80)
    print("VERIFICATION: Final state")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE company_name LIKE '%,%') as has_comma,
            COUNT(*) FILTER (WHERE company_name NOT LIKE '%,%') as no_comma
        FROM clients;
    """)
    
    total, has_comma, no_comma = cur.fetchone()
    print(f"\nTotal clients:              {total}")
    print(f"  With comma (individuals):   {has_comma}")
    print(f"  No comma (companies):       {no_comma}")
    
    # Check for remaining inconsistencies
    cur.execute("""
        SELECT COUNT(*)
        FROM clients
        WHERE corporate_parent_id = 0 
          AND first_name IS NOT NULL
          AND company_name != CONCAT(last_name, ', ', first_name);
    """)
    
    remaining = cur.fetchone()[0]
    if remaining == 0:
        print("\n✅ All individual names are consistent!")
    else:
        print(f"\n⚠️  {remaining} inconsistencies remain")
    
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    if conn:
        conn.rollback()
        conn.close()
    exit(1)
