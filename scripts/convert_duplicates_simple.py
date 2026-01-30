#!/usr/bin/env python3
"""
Convert duplicate client groups to parent-child structure.
Simpler approach: promote one to parent, link others as children.
"""

import os
import psycopg2
import sys

DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

def convert_duplicates_to_parent_child(dry_run=True):
    """Convert all duplicate groups to parent-child relationships."""
    
    conn = psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 140)
    print("CONVERT DUPLICATE CLIENTS TO PARENT-CHILD STRUCTURE (SIMPLE)")
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
    print(f"\nFound {len(duplicates)} duplicate groups\n")
    
    total_groups = 0
    total_children_created = 0
    total_charters_updated = 0
    
    for dup_name, client_ids in duplicates:
        # Find the one with most charters = PARENT
        parent_id = None
        max_charters = -1
        
        for cid in client_ids:
            cur.execute("SELECT COUNT(*) FROM charters WHERE client_id = %s", (cid,))
            charter_count = cur.fetchone()[0]
            if charter_count > max_charters:
                max_charters = charter_count
                parent_id = cid
        
        if not parent_id:
            parent_id = client_ids[0]  # Fallback
        
        child_ids = [cid for cid in client_ids if cid != parent_id]
        
        if dry_run:
            print(f"  {dup_name}: {len(client_ids)} copies")
            print(f"    Parent: ID {parent_id} ({max_charters} charters)")
            print(f"    Children: {child_ids}")
        else:
            # Link all children to parent
            for child_id in child_ids:
                cur.execute("UPDATE clients SET parent_client_id = %s WHERE client_id = %s",
                           (parent_id, child_id))
                total_children_created += 1
            
            # Update charters from children to point to parent
            cur.execute(f"SELECT COUNT(*) FROM charters WHERE client_id = ANY(%s)", (child_ids,))
            charters_count = cur.fetchone()[0]
            
            cur.execute(f"UPDATE charters SET client_id = %s WHERE client_id = ANY(%s)",
                       (parent_id, child_ids))
            
            total_charters_updated += charters_count
            
            print(f"  ✓ {dup_name}: {len(child_ids)} children linked to parent {parent_id} ({charters_count} charters updated)")
        
        total_groups += 1
        conn.commit() if not dry_run else None
    
    # Summary
    print(f"\n{'='*140}")
    print("SUMMARY")
    print(f"{'='*140}")
    
    if dry_run:
        print(f"\nProcessing: {total_groups} duplicate groups")
        print(f"\nTo apply changes, run:")
        print(f"  python convert_duplicates_to_parent_child_fixed.py --write")
    else:
        print(f"\n✓ Converted: {total_groups} duplicate groups")
        print(f"✓ Parent-child links created: {total_children_created}")
        print(f"✓ Charters updated: {total_charters_updated}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    dry_run = '--write' not in sys.argv
    convert_duplicates_to_parent_child(dry_run=dry_run)
