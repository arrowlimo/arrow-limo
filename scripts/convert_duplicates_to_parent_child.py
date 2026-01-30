#!/usr/bin/env python3
"""
Convert duplicate client groups to parent-child structure.
15 groups identified with different regional contact info.
"""

import os
import psycopg2
import sys
from datetime import datetime

DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

def convert_duplicates_to_parent_child(dry_run=True):
    """Convert all 15 duplicate groups to parent-child relationships."""
    
    conn = psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 140)
    print("CONVERT DUPLICATE CLIENTS TO PARENT-CHILD STRUCTURE")
    print("=" * 140)
    print(f"\nMode: {'DRY-RUN (preview)' if dry_run else 'WRITE (apply changes)'}")
    
    # Get all duplicate names with their client_ids
    cur.execute("""
        SELECT client_name, array_agg(client_id ORDER BY client_id) as ids
        FROM clients
        WHERE client_name IS NOT NULL 
          AND parent_client_id IS NULL
        GROUP BY client_name
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
    """)
    
    duplicates = cur.fetchall()
    print(f"\nFound {len(duplicates)} duplicate groups")
    
    total_conversions = 0
    total_charters_affected = 0
    
    for group_idx, (dup_name, client_ids) in enumerate(duplicates, 1):
        print(f"\n{'='*140}")
        print(f"[{group_idx}/{len(duplicates)}] {dup_name}")
        print(f"{'='*140}")
        print(f"Current IDs: {client_ids}")
        
        # Get info for each client in this group
        for cid in client_ids:
            cur.execute("""
                SELECT client_id, company_name, client_name, primary_phone, email, 
                       address_line1, city, (SELECT COUNT(*) FROM charters WHERE client_id = %s) as charters
                FROM clients WHERE client_id = %s
            """, (cid, cid))
            info = cur.fetchone()
            if info:
                print(f"  ID {info[0]}: {info[5]}, {info[6]} | {info[3]} | {info[4]} ({info[7]} charters)")
        
        if dry_run:
            print(f"  [DRY-RUN] Would convert:")
            print(f"    - Keep largest (most charters) as NEW PARENT")
            print(f"    - Convert others to CHILDREN with parent_client_id")
            total_conversions += 1
        else:
            # Find which one has most charters (keep as parent)
            cur.execute(f"""
                SELECT client_id, COUNT(charter_id) as charter_count
                FROM clients c
                LEFT JOIN charters ch ON ch.client_id = c.client_id
                WHERE c.client_id = ANY(%s)
                GROUP BY c.client_id
                ORDER BY charter_count DESC
                LIMIT 1
            """, (client_ids,))
            
            primary_id = cur.fetchone()[0]
            print(f"  Primary (parent): ID {primary_id}")
            
            # Create NEW parent with both company_name and consolidated info
            cur.execute("""
                SELECT company_name, primary_phone, email, address_line1, city
                FROM clients WHERE client_id = %s
            """, (primary_id,))
            
            primary_info = cur.fetchone()
            company_name = primary_info[0] or dup_name
            
            # Insert new parent (copy of primary with no parent_client_id)
            cur.execute("""
                INSERT INTO clients 
                (company_name, client_name, is_company, primary_phone, email, 
                 address_line1, city, created_at)
                VALUES (%s, NULL, true, %s, %s, %s, %s, NOW())
                RETURNING client_id
            """, (company_name, primary_info[1], primary_info[2], 
                  primary_info[3], primary_info[4]))
            
            new_parent_id = cur.fetchone()[0]
            print(f"  New parent created: ID {new_parent_id}")
            
            # Convert each child
            for child_old_id in client_ids:
                if child_old_id != primary_id:
                    # Update to set parent_client_id
                    cur.execute("""
                        UPDATE clients 
                        SET parent_client_id = %s, is_company = false
                        WHERE client_id = %s
                    """, (new_parent_id, child_old_id))
                    
                    print(f"    ✓ ID {child_old_id} → child of {new_parent_id}")
            
            # Update primary to also be a child
            cur.execute("""
                UPDATE clients 
                SET parent_client_id = %s, is_company = false
                WHERE client_id = %s
            """, (new_parent_id, primary_id))
            
            print(f"    ✓ ID {primary_id} → child of {new_parent_id}")
            
            # Update all charters to point to new parent
            cur.execute(f"""
                SELECT COUNT(*) FROM charters 
                WHERE client_id = ANY(%s)
            """, (client_ids,))
            
            affected_charters = cur.fetchone()[0]
            
            cur.execute(f"""
                UPDATE charters 
                SET client_id = %s
                WHERE client_id = ANY(%s)
            """, (new_parent_id, client_ids))
            
            print(f"    ✓ Updated {affected_charters} charters → parent ID {new_parent_id}")
            
            conn.commit()
            total_conversions += 1
            total_charters_affected += affected_charters
    
    # Summary
    print(f"\n{'='*140}")
    print("CONVERSION COMPLETE")
    print(f"{'='*140}")
    
    if dry_run:
        print(f"\nWould process: {total_conversions} duplicate groups")
        print(f"\nTo apply these changes, run:")
        print(f"  python convert_duplicates_to_parent_child.py --write")
    else:
        print(f"\n✓ Converted: {total_conversions} duplicate groups")
        print(f"✓ Charters updated: {total_charters_affected}")
        print(f"\nVerify with:")
        print(f"  SELECT * FROM clients WHERE parent_client_id IS NOT NULL ORDER BY parent_client_id;")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    dry_run = '--write' not in sys.argv
    convert_duplicates_to_parent_child(dry_run=dry_run)
