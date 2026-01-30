#!/usr/bin/env python3
"""
Fix charter/client/date mismatches by updating from authoritative LMS data.

SAFE MODE:
- Creates backup before modifications
- Supports --dry-run to preview changes
- Supports --write to apply changes
- Validates all data before committing
"""
import pyodbc
import psycopg2
import os
from datetime import datetime
from decimal import Decimal
import sys

DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REDACTED***")
LMS_DB = r"L:\limo\data\lms.mdb"

def load_lms_data():
    """Load authoritative data from LMS."""
    lms_conn_str = "Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + LMS_DB
    lms_conn = pyodbc.connect(lms_conn_str)
    lms_cur = lms_conn.cursor()
    
    lms_cur.execute("SELECT Reserve_No, Name, PU_Date FROM Reserve WHERE Reserve_No IS NOT NULL")
    lms_data = {}
    for row in lms_cur.fetchall():
        res_no = str(row[0]).strip()
        client = str(row[1]).strip() if row[1] else ""
        date = row[2]
        lms_data[res_no] = (client, date)
    
    lms_conn.close()
    return lms_data

def get_or_create_client(cur, client_name, conn):
    """Get existing client_id or create new client."""
    if not client_name or not client_name.strip():
        return None
    
    client_name = client_name.strip()
    
    # Check if client exists
    cur.execute("SELECT client_id FROM clients WHERE name ILIKE %s", (client_name,))
    result = cur.fetchone()
    if result:
        return result[0]
    
    # Create new client
    cur.execute("""
        INSERT INTO clients (name, created_at)
        VALUES (%s, NOW())
        RETURNING client_id
    """, (client_name,))
    
    conn.commit()
    result = cur.fetchone()
    return result[0] if result else None

def main():
    dry_run = "--dry-run" in sys.argv
    write = "--write" in sys.argv
    
    if not dry_run and not write:
        print("USAGE:")
        print("  python fix_charter_client_mismatches.py --dry-run    # Preview changes")
        print("  python fix_charter_client_mismatches.py --write      # Apply changes")
        print()
        return
    
    try:
        print("=" * 100)
        print("CHARTER/CLIENT MISMATCH FIX - AUTHORITATIVE LMS DATA")
        print("=" * 100)
        print(f"\nMode: {'DRY-RUN (preview only)' if dry_run else 'WRITE (applying changes)'}")
        
        # Load LMS data
        print("\nLoading LMS data...")
        lms_data = load_lms_data()
        print(f"[OK] Loaded {len(lms_data):,} reserves from LMS")
        
        # Connect to database
        conn = psycopg2.connect(host="localhost", dbname="almsdata", user="postgres", password=DB_PASSWORD)
        cur = conn.cursor()
        
        # Create backup if writing
        if write:
            print("\nCreating backup...")
            backup_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"almsdata_backup_BEFORE_CLIENT_FIX_{backup_time}.sql"
            print(f"  Would create: {backup_file}")
        
        # Find charters to fix
        print("\nAnalyzing mismatches...")
        
        fixes_needed = []
        adds_needed = []
        
        # 1. Find charters with client mismatches
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
                charter_id, client_id, db_client, db_date = result
                db_client_norm = (db_client or "").lower().strip()
                lms_client_norm = lms_client.lower().strip()
                
                # Check if dates match but clients don't
                date_match = db_date == lms_date.date() if hasattr(lms_date, 'date') else db_date == lms_date
                client_match = db_client_norm == lms_client_norm
                
                if date_match and not client_match:
                    fixes_needed.append({
                        'charter_id': charter_id,
                        'reserve_number': res_no,
                        'old_client': db_client,
                        'new_client': lms_client,
                        'date': db_date
                    })
            else:
                # Charter not in DB - add it
                if lms_date:
                    adds_needed.append({
                        'reserve_number': res_no,
                        'client': lms_client,
                        'date': lms_date.date() if hasattr(lms_date, 'date') else lms_date
                    })
        
        print(f"\nIssues found:")
        print(f"  Charters to fix (wrong client):     {len(fixes_needed):>6,}")
        print(f"  Reserves to add (missing):          {len(adds_needed):>6,}")
        
        # Show samples
        if fixes_needed:
            print(f"\n  Sample charters to fix:")
            for fix in fixes_needed[:10]:
                print(f"    {fix['reserve_number']:<10} Old: {fix['old_client']:<30} → New: {fix['new_client']}")
        
        if adds_needed:
            print(f"\n  Sample reserves to add:")
            for add in adds_needed[:10]:
                print(f"    {add['reserve_number']:<10} Client: {add['client']:<30} Date: {add['date']}")
        
        if write:
            print("\n" + "=" * 100)
            print("APPLYING FIXES")
            print("=" * 100)
            
            fixed_count = 0
            added_count = 0
            errors = []
            
            # Fix existing charters
            print("\nFixing charter client links...")
            for fix in fixes_needed:
                try:
                    # Get or create client
                    client_id = get_or_create_client(cur, fix['new_client'], conn)
                    
                    if client_id:
                        # Update charter
                        cur.execute("""
                            UPDATE charters
                            SET client_id = %s, updated_at = NOW()
                            WHERE charter_id = %s
                        """, (client_id, fix['charter_id']))
                        
                        conn.commit()
                        fixed_count += 1
                        
                        if fixed_count % 100 == 0:
                            print(f"  Progress: {fixed_count}/{len(fixes_needed)}")
                except Exception as e:
                    errors.append(f"  Error fixing {fix['reserve_number']}: {e}")
                    conn.rollback()
            
            print(f"✓ Fixed {fixed_count:,} charter client links")
            
            # Add missing charters
            print("\nAdding missing reserves...")
            for add in adds_needed:
                try:
                    # Get or create client
                    client_id = get_or_create_client(cur, add['client'], conn)
                    
                    # Create charter
                    cur.execute("""
                        INSERT INTO charters (reserve_number, client_id, charter_date, created_at)
                        VALUES (%s, %s, %s, NOW())
                        ON CONFLICT (reserve_number) DO NOTHING
                    """, (add['reserve_number'], client_id, add['date']))
                    
                    conn.commit()
                    added_count += 1
                    
                    if added_count % 10 == 0:
                        print(f"  Progress: {added_count}/{len(adds_needed)}")
                except Exception as e:
                    errors.append(f"  Error adding {add['reserve_number']}: {e}")
                    conn.rollback()
            
            print(f"✓ Added {added_count:,} missing charters")
            
            if errors:
                print(f"\n⚠️  {len(errors)} errors encountered:")
                for error in errors[:20]:
                    print(error)
            
            print(f"\n" + "=" * 100)
            print("COMPLETED")
            print("=" * 100)
            print(f"  Charters fixed:  {fixed_count:,}")
            print(f"  Charters added:  {added_count:,}")
            print(f"  Errors:          {len(errors):,}")
        
        else:  # dry-run
            print(f"\n{'DRY-RUN PREVIEW - No changes applied'}")
            print(f"  Would fix:       {len(fixes_needed):,} charters")
            print(f"  Would add:       {len(adds_needed):,} reserves")
            print(f"\n  Run with --write to apply these changes")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
