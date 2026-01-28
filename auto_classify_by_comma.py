#!/usr/bin/env python3
"""
Auto-classify based on comma pattern:
- Has comma: Individual "Last, First" → split, corporate_parent_id=0
- No comma: Company name → corporate_parent_id=0
"""
import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Step 1: Identify patterns
    print("=" * 80)
    print("AUTO-CLASSIFY: Comma = Individual, No Comma = Company")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE company_name LIKE '%,%') as has_comma,
            COUNT(*) FILTER (WHERE company_name NOT LIKE '%,%') as no_comma,
            COUNT(*) as total
        FROM clients
        WHERE corporate_parent_id = 1;
    """)
    
    has_comma, no_comma, total = cur.fetchone()
    print(f"\nClients with corporate_parent_id=1 (uncertain):")
    print(f"  Has comma (individuals):    {has_comma}")
    print(f"  No comma (companies):       {no_comma}")
    print(f"  Total:                      {total}\n")
    
    # Step 2: Split comma names (individuals)
    print("=" * 80)
    print("PROCESSING: Individuals with comma")
    print("=" * 80)
    
    cur.execute("""
        SELECT client_id, company_name
        FROM clients
        WHERE corporate_parent_id = 1
          AND company_name LIKE '%,%'
        ORDER BY company_name
        LIMIT 20
    """)
    
    samples = cur.fetchall()
    print(f"\nSample comma-separated names (first 20):")
    for client_id, name in samples:
        parts = name.split(',')
        if len(parts) == 2:
            last_name = parts[0].strip()
            first_name = parts[1].strip()
            print(f"  ID {client_id}: '{name}' → last='{last_name}', first='{first_name}'")
    
    # Confirm step 1
    print("\n" + "=" * 80)
    response = input(f"Mark all {has_comma} comma-separated names as individuals (corporate_parent_id=0)? [y/N]: ").strip().lower()
    
    if response == 'y':
        print("🔄 Splitting comma-separated names...")
        
        cur.execute("""
            UPDATE clients
            SET 
                first_name = NULLIF(trim(split_part(company_name, ',', 2)), ''),
                last_name = NULLIF(trim(split_part(company_name, ',', 1)), ''),
                corporate_parent_id = 0,
                corporate_role = NULL
            WHERE corporate_parent_id = 1
              AND company_name LIKE '%,%';
        """)
        
        conn.commit()
        print(f"✅ Updated {cur.rowcount} individuals")
    else:
        print("❌ Cancelled")
        conn.close()
        exit(0)
    
    # Step 2 SKIPPED: Companies without comma (conservative approach)
    # Note: Skipping non-comma classification to avoid false positives
    # from Oriental names and other multi-word patterns.
    # These will be manually reviewed later.
    
    print("\n" + "=" * 80)
    print("SKIPPING: Non-comma names (conservative approach)")
    print("=" * 80)
    
    cur.execute("""
        SELECT COUNT(*)
        FROM clients
        WHERE corporate_parent_id = 1
          AND company_name NOT LIKE '%,%';
    """)
    remaining_total = cur.fetchone()[0]
    
    print(f"\nNon-comma names remaining for manual review: {remaining_total}")
    print("(These may include: companies, Oriental names, or other patterns)")
    
    # Final verification
    print("\n" + "=" * 80)
    print("VERIFICATION: Final state")
    print("=" * 80)
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE corporate_parent_id = 0) as individuals_and_companies,
            COUNT(*) FILTER (WHERE corporate_parent_id = 1) as uncertain,
            COUNT(*) FILTER (WHERE corporate_parent_id > 1) as grouped,
            COUNT(*) as total
        FROM clients;
    """)
    
    cleared, uncertain, grouped, total = cur.fetchone()
    print(f"corporate_parent_id = 0:  {cleared} (individuals + standalone companies)")
    print(f"corporate_parent_id = 1:  {uncertain} (remaining uncertain)")
    print(f"corporate_parent_id > 1:  {grouped} (company groups)")
    print(f"Total:                    {total}")
    
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    if conn:
        conn.rollback()
        conn.close()
    exit(1)
