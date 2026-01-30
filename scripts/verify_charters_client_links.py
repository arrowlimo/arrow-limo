#!/usr/bin/env python3
"""
Verify charters are correctly linked to clients with proper name mapping.

LOGIC:
- Corporations: Use company_name (NOT client_name or first/last name)
- Individuals: Use client_name OR first_name/last_name
- Match LMS Name to correct ALMS client field based on entity type
"""

import os
import sys
import psycopg2
import pyodbc
from datetime import datetime

DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REDACTED***')
LMS_PATH = r"L:\limo\database_backups\lms2026.mdb"

def get_alms_conn():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password=DB_PASSWORD
    )

def get_lms_data():
    """Load LMS reserve data with client names."""
    access_conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};"
    access_conn = pyodbc.connect(access_conn_str)
    access_cur = access_conn.cursor()
    
    # Get Reserve -> Name mapping
    access_cur.execute("SELECT Reserve_No, Name FROM Reserve WHERE Reserve_No IS NOT NULL")
    lms_data = {str(row[0]).strip(): str(row[1]).strip() if row[1] else "" for row in access_cur.fetchall()}
    
    access_conn.close()
    return lms_data

def main(dry_run=True):
    print("=" * 100)
    print("VERIFY CHARTERS CLIENT LINKS - LMS TO ALMS MAPPING")
    print("=" * 100)
    print(f"\nMode: {'DRY-RUN (preview only)' if dry_run else 'WRITE (applying fixes)'}")
    
    # Load LMS data
    print("\nLoading LMS reserve names...")
    lms_data = get_lms_data()
    print(f"[OK] Loaded {len(lms_data):,} reserves from LMS")
    
    # Connect to ALMS
    conn = get_alms_conn()
    cur = conn.cursor()
    
    # Find charters with NULL client_id
    print("\nAnalyzing charter-client links...")
    cur.execute("""
        SELECT COUNT(*) FROM charters WHERE client_id IS NULL
    """)
    null_client_count = cur.fetchone()[0]
    print(f"Charters with NULL client_id: {null_client_count:,}")
    
    # Analyze client types
    print("\nClient type distribution in ALMS:")
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN is_company = true THEN 1 ELSE 0 END) as corporations,
            SUM(CASE WHEN is_company = false THEN 1 ELSE 0 END) as individuals,
            SUM(CASE WHEN parent_client_id IS NOT NULL THEN 1 ELSE 0 END) as children
        FROM clients
    """)
    total, corps, indivs, children = cur.fetchone()
    print(f"  - Total clients: {total:,}")
    print(f"  - Corporations (is_company=true): {corps:,}")
    print(f"  - Individuals (is_company=false): {indivs:,}")
    print(f"  - Parent-child relationships: {children:,}")
    
    # Check for charters where client_id IS NULL but reserve in LMS
    print("\nFinding fixable charters (NULL client_id + name in LMS)...")
    fixable = 0
    not_found = 0
    
    cur.execute("""
        SELECT charter_id, reserve_number, client_display_name 
        FROM charters 
        WHERE client_id IS NULL AND reserve_number IS NOT NULL
        ORDER BY reserve_number
        LIMIT 100
    """)
    
    sample_fixes = []
    for charter_id, reserve_no, display_name in cur.fetchall():
        if reserve_no.strip() in lms_data:
            lms_name = lms_data[reserve_no.strip()]
            fixable += 1
            sample_fixes.append((charter_id, reserve_no, display_name, lms_name))
        else:
            not_found += 1
    
    print(f"  - Can fix by LMS name match: {fixable}")
    print(f"  - Not found in LMS: {not_found}")
    
    if sample_fixes:
        print(f"\n  Sample of {min(5, len(sample_fixes))} fixable charters:")
        for charter_id, reserve_no, disp_name, lms_name in sample_fixes[:5]:
            print(f"    Charter #{charter_id} | Reserve {reserve_no}")
            print(f"      Current display: {disp_name}")
            print(f"      LMS name: {lms_name}")
    
    # Name matching strategy
    print("\n" + "=" * 100)
    print("NAME MATCHING STRATEGY")
    print("=" * 100)
    print("""
For each LMS Name → Find matching ALMS client:

1. EXACT MATCH (preferred)
   - Is_company=true: Match against company_name (case-insensitive)
   - Is_company=false: Match against client_name OR (first_name + last_name)

2. PARTIAL MATCH (fallback)
   - Search for LMS name in company_name OR client_name

3. PARENT-CHILD MAPPING (if LMS has parent/child)
   - Link child charter to parent_client_id in ALMS
   - Track via parent_client_id field in clients table
    """)
    
    # Show potential name matching issues
    print("\n" + "=" * 100)
    print("POTENTIAL NAME MAPPING ISSUES")
    print("=" * 100)
    
    # Check for duplicate client names
    cur.execute("""
        SELECT client_name, COUNT(*) as cnt 
        FROM clients 
        WHERE client_name IS NOT NULL 
        GROUP BY client_name 
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
        LIMIT 10
    """)
    
    duplicates = cur.fetchall()
    if duplicates:
        print(f"\nDuplicate client names (possible duplicates to merge):")
        for name, cnt in duplicates:
            print(f"  - '{name}': {cnt} clients")
    else:
        print("\nNo duplicate client names found.")
    
    # Check for company name variations
    cur.execute("""
        SELECT company_name, COUNT(*) as cnt 
        FROM clients 
        WHERE company_name IS NOT NULL 
        GROUP BY company_name 
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
        LIMIT 10
    """)
    
    comp_dups = cur.fetchall()
    if comp_dups:
        print(f"\nDuplicate company names (possible duplicates to merge):")
        for name, cnt in comp_dups:
            print(f"  - '{name}': {cnt} clients")
    else:
        print("\nNo duplicate company names found.")
    
    # Verify charters without client but with charter display name
    print("\n" + "=" * 100)
    print("NEXT STEPS")
    print("=" * 100)
    print("""
1. Run: python verify_charters_client_links.py --write
   - Maps LMS names to ALMS clients by exact/partial match
   - Updates charter.client_id with matched client_id
   - Updates charter.client_display_name from client's primary name

2. Run: python link_charters_to_clients_by_account.py --write
   - Links via account_number (secondary method)

3. Audit remaining NULL client_ids
   - Manually create clients for names not in ALMS
   - Review parent-child relationships in LMS vs ALMS
    """)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    dry_run = '--write' not in sys.argv
    main(dry_run=dry_run)
