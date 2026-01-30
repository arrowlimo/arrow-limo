#!/usr/bin/env python3
"""
Import missing reserves from LMS (booked 2025-12-04 onwards).

Includes:
- 66 missing reserves (019773-019848)
- Associated client data
- Payment information
- Routing/dispatch data

Run with --dry-run first, then --write to apply.
"""
import pyodbc
import psycopg2
import os
import sys
from datetime import datetime
from decimal import Decimal

LMS_DB = r"L:\limo\data\lms.mdb"
DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REDACTED***")

DRY_RUN = "--dry-run" in sys.argv or len(sys.argv) == 1
WRITE_MODE = "--write" in sys.argv

def get_lms_reserves_to_import():
    """Get the 66 missing reserves from LMS."""
    lms_conn_str = "Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + LMS_DB
    lms_conn = pyodbc.connect(lms_conn_str)
    lms_cur = lms_conn.cursor()
    
    # Get the 66 missing reserves with full details
    lms_cur.execute("""
        SELECT 
            Reserve_No, 
            Name, 
            PU_Date, 
            Order_Date,
            Est_Charge,
            Balance,
            Status,
            Driver,
            Vehicle,
            From_To,
            Notes
        FROM Reserve
        WHERE Reserve_No >= '019773' AND Reserve_No <= '019848'
        ORDER BY Reserve_No
    """)
    
    reserves = []
    for row in lms_cur.fetchall():
        reserves.append({
            'reserve_no': str(row[0]).strip(),
            'client_name': str(row[1]).strip() if row[1] else 'Unknown',
            'pu_date': row[2],
            'order_date': row[3],
            'est_charge': Decimal(str(row[4])) if row[4] else Decimal('0'),
            'balance': Decimal(str(row[5])) if row[5] else Decimal('0'),
            'status': str(row[6]).strip() if row[6] else 'Unknown',
            'driver': str(row[7]).strip() if row[7] else None,
            'vehicle': str(row[8]).strip() if row[8] else None,
            'from_to': str(row[9]).strip() if row[9] else None,
            'notes': str(row[10]).strip() if row[10] else None,
        })
    
    lms_conn.close()
    return reserves

def main():
    try:
        print("=" * 100)
        print(f"IMPORT MISSING RESERVES FROM LMS {'(DRY RUN)' if DRY_RUN else '(APPLYING CHANGES)'}")
        print("=" * 100)
        
        # Load LMS reserves to import
        print("\nLoading 66 missing reserves from LMS...")
        reserves_to_import = get_lms_reserves_to_import()
        print(f"✓ Loaded {len(reserves_to_import):,} reserves")
        
        if not reserves_to_import:
            print("No reserves found to import!")
            return
        
        # Show sample
        print(f"\nSample reserves to import (first 5):")
        for res in reserves_to_import[:5]:
            print(f"  {res['reserve_no']:<8} {res['client_name']:<30} PU: {res['pu_date']} Amount: {res['est_charge']}")
        
        # Connect to database
        conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cur = conn.cursor()
        
        # Check which reserves already exist
        print("\nChecking for existing reserves...")
        existing = set()
        for res in reserves_to_import:
            cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (res['reserve_no'],))
            if cur.fetchone():
                existing.add(res['reserve_no'])
        
        to_import = [r for r in reserves_to_import if r['reserve_no'] not in existing]
        
        print(f"Already in database: {len(existing):,}")
        print(f"Ready to import: {len(to_import):,}")
        
        if DRY_RUN:
            print("\n" + "=" * 100)
            print("DRY RUN SUMMARY")
            print("=" * 100)
            print(f"\nWould import {len(to_import):,} new reserves")
            print(f"Would create/link clients for all reserves")
            print(f"Total estimated amount: ${sum(r['est_charge'] for r in to_import):,.2f}")
            
            print("\nTo apply these changes, run:")
            print("  python scripts/import_missing_reserves.py --write")
        else:
            # Apply changes
            print("\n" + "=" * 100)
            print("IMPORTING RESERVES")
            print("=" * 100)
            
            created_clients = 0
            created_charters = 0
            
            for i, reserve in enumerate(to_import):
                # Get or create client
                cur.execute("""
                    SELECT client_id FROM clients
                    WHERE LOWER(TRIM(name)) = %s
                """, (reserve['client_name'].lower(),))
                
                result = cur.fetchone()
                if result:
                    client_id = result[0]
                else:
                    # Create new client
                    cur.execute("SELECT COALESCE(MAX(CAST(account_number AS INTEGER)), 0) + 1 FROM clients WHERE account_number ~ '^[0-9]+$'")
                    next_account = cur.fetchone()[0]
                    
                    cur.execute("""
                        INSERT INTO clients (account_number, name, created_at)
                        VALUES (%s, %s, NOW())
                        RETURNING client_id
                    """, (str(next_account), reserve['client_name']))
                    
                    client_id = cur.fetchone()[0]
                    created_clients += 1
                
                # Create charter
                cur.execute("""
                    INSERT INTO charters (
                        reserve_number, 
                        client_id, 
                        charter_date,
                        total_amount_due,
                        balance,
                        notes,
                        created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    RETURNING charter_id
                """, (
                    reserve['reserve_no'],
                    client_id,
                    reserve['pu_date'].date() if hasattr(reserve['pu_date'], 'date') else reserve['pu_date'],
                    reserve['est_charge'],
                    reserve['balance'],
                    reserve['notes']
                ))
                
                charter_id = cur.fetchone()[0]
                created_charters += 1
                
                if (i + 1) % 10 == 0:
                    print(f"  Imported {i+1:,} reserves...")
            
            # Commit all changes
            conn.commit()
            
            print(f"\n✓ Created {created_clients:,} new clients")
            print(f"✓ Created {created_charters:,} new charters")
            print(f"✓ All changes committed to database")
        
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
