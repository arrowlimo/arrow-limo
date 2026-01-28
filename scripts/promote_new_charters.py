#!/usr/bin/env python3
"""
Promote 3 new charters from lms_staging_reserve to charters table.

These charters were identified as having customers that are now in the clients table.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
import argparse
import json

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD')
    )

def promote_new_charters(conn, dry_run=True):
    """Promote new charters from staging to main table."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("=" * 80)
    print("PROMOTE NEW CHARTERS FROM STAGING")
    print("=" * 80)
    
    # Find charters in staging that are not in main table
    cur.execute("""
        SELECT s.reserve_no, s.raw_data
        FROM lms_staging_reserve s
        WHERE s.raw_data->>'Reserve_No' NOT IN (
            SELECT reserve_number FROM charters
        )
        ORDER BY s.raw_data->>'Reserve_No'
    """)
    
    new_charters = cur.fetchall()
    
    if not new_charters:
        print("\n[OK] No new charters to promote")
        cur.close()
        return
    
    print(f"\nFound {len(new_charters)} new charters to promote")
    
    promoted_count = 0
    skipped_count = 0
    
    for charter in new_charters:
        raw = charter['raw_data']
        reserve_no = raw.get('Reserve_No', '')
        account_no = raw.get('Account_No', '')
        
        print(f"\n{'─' * 80}")
        print(f"Charter: {reserve_no} (Account: {account_no})")
        
        # Check if customer exists
        cur.execute("""
            SELECT client_id, client_name 
            FROM clients 
            WHERE account_number = %s
        """, (account_no,))
        
        client = cur.fetchone()
        
        if not client:
            print(f"  [WARN]  SKIP: Customer {account_no} not found in clients table")
            skipped_count += 1
            continue
        
        print(f"  [OK] Customer found: {client['client_name']} (ID {client['client_id']})")
        
        # Extract charter data from raw_data
        charter_data = {
            'reserve_number': reserve_no,
            'account_number': account_no,
            'client_id': client['client_id'],
            'charter_date': raw.get('PU_Date'),
            'pickup_time': raw.get('PU_Time'),
            'pickup_address': raw.get('PU_Address'),
            'dropoff_address': raw.get('DO_Address'),
            'passenger_count': raw.get('No_Pass'),
            'vehicle': raw.get('Vehicle'),
            'driver': raw.get('Driver'),
            'rate': raw.get('Rate'),
            'balance': raw.get('Balance'),
            'deposit': raw.get('Deposit'),
            'status': raw.get('Status'),
            'notes': raw.get('Notes'),
        }
        
        print(f"  Date: {charter_data['charter_date']}")
        print(f"  Pickup: {charter_data['pickup_address']}")
        print(f"  Rate: ${charter_data['rate']}")
        print(f"  Balance: ${charter_data['balance']}")
        
        if dry_run:
            print(f"  🔍 DRY RUN - Would insert charter")
        else:
            # Insert into charters table
            cur.execute("""
                INSERT INTO charters (
                    reserve_number, account_number, client_id,
                    charter_date, pickup_time, pickup_address, dropoff_address,
                    passenger_count, vehicle, driver, rate, balance, deposit,
                    status, notes
                ) VALUES (
                    %(reserve_number)s, %(account_number)s, %(client_id)s,
                    %(charter_date)s, %(pickup_time)s, %(pickup_address)s, %(dropoff_address)s,
                    %(passenger_count)s, %(vehicle)s, %(driver)s, %(rate)s, %(balance)s, %(deposit)s,
                    %(status)s, %(notes)s
                )
                RETURNING charter_id
            """, charter_data)
            
            charter_id = cur.fetchone()['charter_id']
            print(f"  [OK] Inserted as charter_id {charter_id}")
            promoted_count += 1
    
    print(f"\n{'=' * 80}")
    print(f"SUMMARY:")
    print(f"{'=' * 80}")
    print(f"  Promoted: {promoted_count}")
    print(f"  Skipped: {skipped_count}")
    
    if not dry_run:
        conn.commit()
        print(f"\n[OK] Changes committed to database")
    else:
        print(f"\n🔍 DRY RUN - No changes made")
        print(f"   Run with --write to apply changes")
    
    cur.close()

def main():
    parser = argparse.ArgumentParser(description='Promote new charters from staging')
    parser.add_argument('--write', action='store_true', 
                       help='Apply changes (default is dry-run)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    
    if args.write:
        print("\n[WARN]  WRITE MODE - Changes will be applied!")
    else:
        print("\n🔍 DRY RUN MODE - No changes will be made")
    
    promote_new_charters(conn, dry_run=not args.write)
    
    conn.close()

if __name__ == '__main__':
    main()
