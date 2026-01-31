#!/usr/bin/env python3
"""
Analyze duplicate clients to see if they have different contact info.
If different info exists, create parent-child relationship instead of consolidating.
If same info, consolidate to single client.
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
    
    print("=" * 140)
    print("DUPLICATE CLIENT ANALYSIS - INFO DIFFERENCES")
    print("=" * 140)
    
    # Get duplicate names (not in parent-child)
    cur.execute("""
        SELECT client_name, STRING_AGG(client_id::text, ', ' ORDER BY client_id) as ids
        FROM clients
        WHERE client_name IS NOT NULL 
          AND parent_client_id IS NULL
        GROUP BY client_name
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
    """)
    
    duplicates = cur.fetchall()
    
    print(f"\nAnalyzing {len(duplicates)} duplicate client names:\n")
    
    consolidate_list = []
    parent_child_candidates = []
    
    for dup_name, id_list in duplicates[:15]:  # Check top 15
        ids = [int(x.strip()) for x in id_list.split(',')]
        
        print(f"\n{'='*140}")
        print(f"CLIENT NAME: {dup_name}")
        print(f"IDs: {ids}")
        print(f"{'='*140}")
        
        # Get detailed info for each duplicate
        client_info = {}
        for client_id in ids:
            cur.execute("""
                SELECT client_id, company_name, primary_phone, email, address_line1, city, 
                       (SELECT COUNT(*) FROM charters WHERE client_id = %s) as charter_count
                FROM clients
                WHERE client_id = %s
            """, (client_id, client_id))
            
            row = cur.fetchone()
            if row:
                client_info[client_id] = {
                    'company': row[1],
                    'phone': row[2],
                    'email': row[3],
                    'address': row[4],
                    'city': row[5],
                    'charters': row[6]
                }
        
        # Display info
        for client_id in ids:
            info = client_info[client_id]
            print(f"\n  ID {client_id} ({info['charters']} charters):")
            print(f"    Company: {info['company']}")
            print(f"    Phone:   {info['phone']}")
            print(f"    Email:   {info['email']}")
            print(f"    Address: {info['address']}, {info['city']}")
        
        # Analyze differences
        print(f"\n  ANALYSIS:")
        
        # Check if all same
        unique_phones = set(info['phone'] for info in client_info.values())
        unique_emails = set(info['email'] for info in client_info.values())
        unique_addresses = set(info['address'] for info in client_info.values())
        unique_cities = set(info['city'] for info in client_info.values())
        
        different_fields = []
        if len(unique_phones) > 1 and any(unique_phones):
            different_fields.append("PHONE")
        if len(unique_emails) > 1 and any(unique_emails):
            different_fields.append("EMAIL")
        if len(unique_addresses) > 1 and any(unique_addresses):
            different_fields.append("ADDRESS")
        if len(unique_cities) > 1 and any(unique_cities):
            different_fields.append("CITY")
        
        if different_fields:
            print(f"    ⚠️  DIFFERENT INFO FOUND: {', '.join(different_fields)}")
            print(f"    → CANDIDATE FOR PARENT-CHILD STRUCTURE")
            parent_child_candidates.append((dup_name, ids, different_fields))
        else:
            print(f"    ✓ Same contact info (or all empty)")
            print(f"    → CANDIDATE FOR CONSOLIDATION")
            consolidate_list.append((dup_name, ids))
    
    # Summary
    print(f"\n\n{'='*140}")
    print("CONSOLIDATION STRATEGY SUMMARY")
    print(f"{'='*140}")
    
    print(f"\n[1] CONSOLIDATE (same info, different IDs):")
    print(f"    {len(consolidate_list)} groups to merge")
    for name, ids in consolidate_list:
        primary = ids[0]  # Keep first with most charters
        cur.execute("SELECT COUNT(*) FROM charters WHERE client_id = ANY(%s)", ([primary],))
        charter_count = cur.fetchone()[0]
        print(f"      • {name}: Keep ID {primary}, merge {len(ids)-1} others ({charter_count} charters)")
    
    print(f"\n[2] PARENT-CHILD STRUCTURE (different contact info):")
    print(f"    {len(parent_child_candidates)} groups to restructure")
    for name, ids, diff_fields in parent_child_candidates:
        print(f"      • {name}: {len(ids)} versions with different {diff_fields}")
        for client_id in ids:
            cur.execute("""
                SELECT COUNT(*) FROM charters WHERE client_id = %s
            """, (client_id,))
            charter_count = cur.fetchone()[0]
            if charter_count > 0:
                print(f"        - ID {client_id}: {charter_count} charters")
    
    print(f"\n{'='*140}")
    print("RECOMMENDATION:")
    print(f"{'='*140}")
    print("""
Option A: CONSOLIDATE ALL
  - Merge all duplicates to primary (most charters)
  - Simpler data model but loses regional/location distinctions

Option B: PARENT-CHILD STRUCTURE  
  - Create parent = main company/client
  - Children = regional offices/locations with different contact info
  - Better for companies with multiple locations
  - Preserves all contact information

Recommended: Option B (parent-child) for companies with different contact info
            Option A (consolidate) for companies with identical/empty info
    """)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
