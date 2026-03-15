#!/usr/bin/env python3
"""
Audit for duplicate clients after parent-child structure creation.
Identify:
1. Duplicate client names NOT in parent-child (true duplicates)
2. Verify parent-child consolidation worked
3. Identify charters linked to wrong duplicates
"""

import os
import psycopg2

DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REDACTED***')

def main():
    conn = psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 120)
    print("DUPLICATE CONSOLIDATION AUDIT")
    print("=" * 120)
    
    # 1. Check parent-child structure created
    print("\n[1] PARENT-CHILD STRUCTURE STATUS")
    print("-" * 120)
    
    cur.execute("""
        SELECT COUNT(*) as total, 
               SUM(CASE WHEN parent_client_id IS NOT NULL THEN 1 ELSE 0 END) as children,
               SUM(CASE WHEN parent_client_id IS NULL THEN 1 ELSE 0 END) as parents
        FROM clients
    """)
    
    total, children, parents = cur.fetchone()
    print(f"Total clients: {total}")
    print(f"  - Parents (no parent_id): {parents}")
    print(f"  - Children (has parent_id): {children}")
    
    # 2. Show parent-child groups
    print("\n[2] PARENT-CHILD GROUPS")
    print("-" * 120)
    
    cur.execute("""
        SELECT parent_client_id, COUNT(*) as child_count,
               STRING_AGG(DISTINCT client_name, ', ') as child_names
        FROM clients
        WHERE parent_client_id IS NOT NULL
        GROUP BY parent_client_id
        ORDER BY child_count DESC
    """)
    
    groups = cur.fetchall()
    print(f"\nCreated {len(groups)} parent-child groups:\n")
    
    for parent_id, child_count, child_names in groups[:10]:
        # Get parent info
        cur.execute("SELECT client_id, company_name, account_number FROM clients WHERE client_id = %s", (parent_id,))
        parent_info = cur.fetchone()
        
        if parent_info:
            print(f"  Parent ID {parent_id}: {parent_info[1]} (Acct: {parent_info[2]})")
            print(f"    └─ {child_count} children: {child_names[:80]}...")
    
    # 3. Find DUPLICATE client names NOT in parent-child (true duplicates to consolidate)
    print("\n\n[3] TRUE DUPLICATES (Not in parent-child structure)")
    print("-" * 120)
    
    cur.execute("""
        SELECT client_name, COUNT(*) as cnt, STRING_AGG(client_id::text, ', ') as ids
        FROM clients
        WHERE client_name IS NOT NULL 
          AND parent_client_id IS NULL  -- Exclude children (they're linked to parent)
        GROUP BY client_name
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
        LIMIT 20
    """)
    
    dups = cur.fetchall()
    if dups:
        print(f"\nFound {len(dups)} duplicate client names (standalone, not in parent-child):\n")
        for name, cnt, ids in dups:
            print(f"  '{name}': {cnt} copies")
            print(f"    IDs: {ids}")
    else:
        print("\nNo duplicate standalone clients found!")
    
    # 4. Check for duplicate company names not in parent-child
    print("\n\n[4] DUPLICATE COMPANY NAMES (Not in parent-child)")
    print("-" * 120)
    
    cur.execute("""
        SELECT company_name, COUNT(*) as cnt, STRING_AGG(client_id::text, ', ') as ids
        FROM clients
        WHERE company_name IS NOT NULL 
          AND parent_client_id IS NULL  -- Only parents
        GROUP BY company_name
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
        LIMIT 20
    """)
    
    comp_dups = cur.fetchall()
    if comp_dups:
        print(f"\nFound {len(comp_dups)} duplicate company names:\n")
        for name, cnt, ids in comp_dups:
            print(f"  '{name}': {cnt} copies")
            print(f"    IDs: {ids}")
    else:
        print("\nNo duplicate company names found!")
    
    # 5. Check for charters linked to duplicate clients
    print("\n\n[5] CHARTERS LINKED TO DUPLICATE CLIENTS")
    print("-" * 120)
    
    # Find charters where client_id is one of the duplicate clients
    cur.execute("""
        WITH dup_clients AS (
            SELECT client_id, client_name FROM clients
            WHERE client_name IS NOT NULL 
              AND parent_client_id IS NULL
              AND client_name IN (
                SELECT client_name FROM clients
                WHERE client_name IS NOT NULL 
                  AND parent_client_id IS NULL
                GROUP BY client_name HAVING COUNT(*) > 1
              )
        )
        SELECT c.client_id, c.client_name, COUNT(ch.charter_id) as charter_count
        FROM dup_clients c
        LEFT JOIN charters ch ON ch.client_id = c.client_id
        GROUP BY c.client_id, c.client_name
        ORDER BY charter_count DESC
    """)
    
    charter_dup_links = cur.fetchall()
    if charter_dup_links:
        print(f"\nCharters linked to duplicate clients:\n")
        for client_id, client_name, charter_count in charter_dup_links:
            print(f"  Client ID {client_id} ({client_name}): {charter_count} charters")
    else:
        print("\nNo charters linked to duplicate clients.")
    
    # 6. Consolidation strategy
    print("\n\n[6] CONSOLIDATION STRATEGY")
    print("-" * 120)
    
    if comp_dups or dups or charter_dup_links:
        print("""
TO CONSOLIDATE DUPLICATES:
1. Identify which duplicate to keep (usually the one with charters)
2. Update all charters from other duplicates to the primary
3. Delete empty duplicate clients
4. Verify all charters linked to single client

Example:
  SELECT * FROM clients WHERE client_name = 'Nova Chemicals' AND parent_client_id IS NULL;
  UPDATE charters SET client_id = <primary_id> WHERE client_id = <duplicate_id>;
  DELETE FROM clients WHERE client_id = <duplicate_id>;
        """)
    else:
        print("""
NO CONSOLIDATION NEEDED - All duplicates resolved by parent-child structure!
        """)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
