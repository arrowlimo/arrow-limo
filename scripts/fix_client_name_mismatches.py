#!/usr/bin/env python3
"""
Fix 3,007 charters with correct dates but missing/wrong client names.

Strategy:
1. Load all LMS client names for valid reserves
2. Find charters with mismatches
3. For each mismatch:
   - If correct client exists: update charter.client_id
   - If correct client doesn't exist: create it, then update charter.client_id
4. Run with --dry-run first, then --write to apply
"""
import pyodbc
import psycopg2
import os
import sys
from datetime import datetime

LMS_DB = r"L:\limo\data\lms.mdb"
DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REDACTED***")

DRY_RUN = "--dry-run" in sys.argv or len(sys.argv) == 1
WRITE_MODE = "--write" in sys.argv

def normalize_name(name):
    """Normalize client name for comparison."""
    if not name:
        return None
    return str(name).strip().lower()

def main():
    try:
        print("=" * 100)
        print(f"FIX CLIENT NAME MISMATCHES {'(DRY RUN - NO CHANGES)' if DRY_RUN else '(APPLYING CHANGES)'}")
        print("=" * 100)
        
        # Load all LMS data
        print("\nLoading legacy LMS data...")
        lms_conn_str = "Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + LMS_DB
        lms_conn = pyodbc.connect(lms_conn_str)
        lms_cur = lms_conn.cursor()
        
        lms_cur.execute("SELECT Reserve_No, Name, PU_Date FROM Reserve WHERE Reserve_No IS NOT NULL")
        lms_data = {}
        for row in lms_cur.fetchall():
            res_no = str(row[0]).strip()
            client = str(row[1]).strip() if row[1] else ""
            pu_date = row[2]
            lms_data[res_no] = (client, pu_date)
        
        lms_conn.close()
        print(f"✓ Loaded {len(lms_data):,} reserves from LMS")
        
        # Connect to database
        conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cur = conn.cursor()
        
        # Find all charters with mismatches
        print("\nAnalyzing charters for client name mismatches...")
        
        mismatches = []
        for res_no in sorted(lms_data.keys()):
            lms_client, lms_date = lms_data[res_no]
            
            cur.execute("""
                SELECT c.charter_id, c.client_id, cl.name, c.charter_date
                FROM charters c
                LEFT JOIN clients cl ON cl.client_id = c.client_id
                WHERE c.reserve_number = %s
            """, (res_no,))
            
            result = cur.fetchone()
            if result:
                charter_id, current_client_id, current_client_name, charter_date = result
                
                # Check if dates match
                date_match = charter_date == lms_date.date() if hasattr(lms_date, 'date') else charter_date == lms_date
                
                if date_match:
                    # Check if client names match
                    current_norm = normalize_name(current_client_name)
                    lms_norm = normalize_name(lms_client)
                    
                    if current_norm != lms_norm:
                        mismatches.append({
                            'charter_id': charter_id,
                            'reserve_no': res_no,
                            'current_client_id': current_client_id,
                            'current_client_name': current_client_name,
                            'lms_client_name': lms_client,
                            'charter_date': charter_date
                        })
        
        print(f"✓ Found {len(mismatches):,} charters with client name mismatches")
        
        # For each mismatch, find or create the correct client
        print("\nProcessing mismatches...")
        
        updates = []
        creates = []
        
        for mismatch in mismatches:
            lms_client_name = mismatch['lms_client_name']
            
            # Check if this client already exists in database
            cur.execute("""
                SELECT client_id FROM clients
                WHERE LOWER(TRIM(name)) = %s
            """, (normalize_name(lms_client_name),))
            
            result = cur.fetchone()
            
            if result:
                # Client exists, just update the charter
                correct_client_id = result[0]
                updates.append({
                    'charter_id': mismatch['charter_id'],
                    'old_client_id': mismatch['current_client_id'],
                    'new_client_id': correct_client_id,
                    'client_name': lms_client_name,
                    'reserve_no': mismatch['reserve_no']
                })
            else:
                # Client doesn't exist, need to create it
                creates.append({
                    'charter_id': mismatch['charter_id'],
                    'old_client_id': mismatch['current_client_id'],
                    'client_name': lms_client_name,
                    'reserve_no': mismatch['reserve_no']
                })
        
        print(f"  Charters needing client update (client exists): {len(updates):,}")
        print(f"  Charters needing new client creation: {len(creates):,}")
        
        # Show samples
        if updates:
            print(f"\n  Sample updates (first 10):")
            for update in updates[:10]:
                print(f"    {update['reserve_no']:<8} → Set client to '{update['client_name']}'")
        
        if creates:
            print(f"\n  Sample new clients to create (first 10):")
            for create in creates[:10]:
                print(f"    {create['reserve_no']:<8} → Create client '{create['client_name']}'")
        
        if DRY_RUN:
            print("\n" + "=" * 100)
            print("DRY RUN SUMMARY")
            print("=" * 100)
            print(f"\nWould apply {len(updates):,} client updates")
            print(f"Would create {len(creates):,} new clients")
            print(f"Total charters fixed: {len(updates) + len(creates):,}")
            print("\nTo apply these changes, run:")
            print("  python scripts/fix_client_name_mismatches.py --write")
        else:
            # Apply changes
            print("\n" + "=" * 100)
            print("APPLYING CHANGES")
            print("=" * 100)
            
            # Create new clients first
            if creates:
                print(f"\nCreating {len(creates):,} new clients...")
                for i, create in enumerate(creates):
                    client_name = create['client_name']
                    
                    # Generate unique account number based on client_id sequence
                    cur.execute("SELECT COALESCE(MAX(CAST(account_number AS INTEGER)), 0) + 1 FROM clients WHERE account_number ~ '^[0-9]+$'")
                    next_account = cur.fetchone()[0]
                    account_number = str(next_account)
                    
                    cur.execute("""
                        INSERT INTO clients (account_number, name, email, phone, address_line1, created_at)
                        VALUES (%s, %s, NULL, NULL, NULL, NOW())
                        RETURNING client_id
                    """, (account_number, client_name))
                    
                    new_client_id = cur.fetchone()[0]
                    
                    # Update updates list to include this new client
                    create['new_client_id'] = new_client_id
                    updates.append({
                        'charter_id': create['charter_id'],
                        'old_client_id': create['old_client_id'],
                        'new_client_id': new_client_id,
                        'client_name': client_name,
                        'reserve_no': create['reserve_no']
                    })
                    
                    if (i + 1) % 500 == 0:
                        print(f"  Created {i+1:,} clients...")
                
                print(f"✓ Created {len(creates):,} new clients")
            
            # Update all charters
            if updates:
                print(f"\nUpdating {len(updates):,} charter client_ids...")
                for i, update in enumerate(updates):
                    cur.execute("""
                        UPDATE charters
                        SET client_id = %s
                        WHERE charter_id = %s
                    """, (update['new_client_id'], update['charter_id']))
                    
                    if (i + 1) % 500 == 0:
                        print(f"  Updated {i+1:,} charters...")
                
                print(f"✓ Updated {len(updates):,} charter client_ids")
            
            # Commit all changes
            conn.commit()
            print("\n✓ All changes committed to database")
        
        cur.close()
        conn.close()
        
        print("\n" + "=" * 100)
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
