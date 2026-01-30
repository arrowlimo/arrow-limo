#!/usr/bin/env python3
"""
Fix client first_name and last_name by parsing client_name in "Last, First" format.
Also fixes parent relationships and account_type field.
"""

import psycopg2
from psycopg2.extras import execute_batch
import os
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def main():
    print(f"\n{'='*80}")
    print(f"FIXING CLIENT NAMES AND RELATIONSHIPS")
    print(f"{'='*80}\n")
    
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    try:
        # Step 1: Parse client_name to populate first_name and last_name for individuals
        print("Step 1: Populating first_name and last_name from client_name...")
        print("-" * 80)
        
        cur.execute("""
            SELECT client_id, client_name, first_name, last_name
            FROM clients
            WHERE is_company = false
            AND (first_name IS NULL OR first_name = '')
            AND client_name LIKE '%,%'
            LIMIT 10
        """)
        
        sample = cur.fetchall()
        print(f"Sample records to parse:")
        for row in sample:
            print(f"  {row[0]}: '{row[1]}' -> first: '{row[2]}', last: '{row[3]}'")
        
        # Parse and update
        print(f"\nUpdating clients...")
        update_count = 0
        
        cur.execute("""
            SELECT client_id, client_name, is_company
            FROM clients
            WHERE is_company = false
        """)
        
        clients = cur.fetchall()
        updates = []
        
        for client_id, client_name, is_company in clients:
            if client_name and ',' in client_name:
                # Parse "Last, First" format
                parts = client_name.split(',', 1)
                last_name = parts[0].strip()
                first_name = parts[1].strip() if len(parts) > 1 else ''
                
                updates.append((first_name, last_name, client_id))
                update_count += 1
        
        if updates:
            execute_batch(
                cur,
                """
                UPDATE clients
                SET first_name = %s, last_name = %s
                WHERE client_id = %s
                """,
                updates,
                page_size=1000
            )
            conn.commit()
            print(f"✅ Updated {update_count} individual clients with parsed names\n")
        
        # Step 2: Fix parent relationships - mark parents as companies
        print("Step 2: Fixing parent relationships...")
        print("-" * 80)
        
        cur.execute("""
            SELECT DISTINCT parent_client_id
            FROM clients
            WHERE parent_client_id IS NOT NULL
        """)
        
        parent_ids = cur.fetchall()
        parent_set = set(row[0] for row in parent_ids)
        
        print(f"Found {len(parent_set)} unique parent IDs")
        
        # Mark parents as companies
        parent_updates = [[pid] for pid in parent_set]
        if parent_updates:
            execute_batch(
                cur,
                """
                UPDATE clients
                SET is_company = true
                WHERE client_id = %s
                """,
                parent_updates,
                page_size=1000
            )
            conn.commit()
            print(f"✅ Updated {len(parent_updates)} parent records to is_company=true\n")
        
        # Step 3: Fix account_type field
        print("Step 3: Setting account_type based on is_company...")
        print("-" * 80)
        
        # Set company
        cur.execute("""
            UPDATE clients
            SET account_type = 'company'
            WHERE is_company = true
        """)
        company_count = cur.rowcount
        
        # Set individual
        cur.execute("""
            UPDATE clients
            SET account_type = 'individual'
            WHERE is_company = false
        """)
        individual_count = cur.rowcount
        
        conn.commit()
        print(f"✅ Updated {company_count} companies, {individual_count} individuals\n")
        
        # Step 4: Verify results
        print("Step 4: Verification...")
        print("-" * 80)
        
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN first_name IS NOT NULL AND first_name <> '' THEN 1 ELSE 0 END) as with_first_name,
                SUM(CASE WHEN is_company THEN 1 ELSE 0 END) as companies,
                SUM(CASE WHEN is_company = false THEN 1 ELSE 0 END) as individuals
            FROM clients
        """)
        
        result = cur.fetchone()
        print(f"Total clients: {result[0]}")
        print(f"With first_name: {result[1]}")
        print(f"Companies: {result[2]}")
        print(f"Individuals: {result[3]}")
        
        # Check for parent errors
        cur.execute("""
            SELECT COUNT(DISTINCT c.parent_client_id) as parent_errors
            FROM clients c
            WHERE c.parent_client_id IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM clients p
                WHERE p.client_id = c.parent_client_id
                AND p.is_company = true
            )
        """)
        
        errors = cur.fetchone()[0]
        print(f"\nParent relationship errors: {errors}")
        
        if errors == 0:
            print("✅ All parent relationships verified!")
        
        print(f"\n{'='*80}")
        print(f"✅ ALL FIXES COMPLETE")
        print(f"{'='*80}\n")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERROR: {e}\n")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
