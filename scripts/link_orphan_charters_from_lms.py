#!/usr/bin/env python3
"""
Link orphan charters by looking up LMS customer names.
Uses: Reserve.Account_No -> Customer.Name (not Attention)
"""

import os
import psycopg2
import pyodbc
import sys
from difflib import SequenceMatcher

DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REDACTED***')
LMS_PATH = r'L:\limo\database_backups\lms2026.mdb'

def similarity(a, b):
    """Calculate string similarity ratio (0.0 to 1.0)"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def link_orphans(dry_run=True):
    """Link orphan charters by LMS customer name lookup."""
    
    # Connect to ALMS
    alms = psycopg2.connect(
        host='localhost', dbname='almsdata', user='postgres',
        password=DB_PASSWORD
    )
    alms_cur = alms.cursor()
    
    # Connect to LMS
    lms = pyodbc.connect(f'Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};')
    lms_cur = lms.cursor()
    
    print("=" * 140)
    print("LINK ORPHAN CHARTERS FROM LMS CUSTOMER NAMES")
    print("=" * 140)
    print(f"\nMode: {'DRY-RUN' if dry_run else 'WRITE'}\n")
    
    # Get all ALMS clients for matching
    alms_cur.execute('''
        SELECT client_id, client_name, company_name, account_number
        FROM clients
        WHERE parent_client_id IS NULL
        ORDER BY client_id
    ''')
    
    alms_clients = {}
    alms_by_account = {}
    for cid, client_name, company_name, account_no in alms_cur.fetchall():
        name = company_name or client_name or ''
        if name:
            alms_clients[cid] = name
            if account_no:
                alms_by_account[account_no] = cid
    
    print(f"ALMS clients loaded: {len(alms_clients)}")
    
    # Get orphan charters
    alms_cur.execute('''
        SELECT charter_id, reserve_number, charter_date, total_amount_due
        FROM charters
        WHERE client_id IS NULL
        ORDER BY charter_date DESC
    ''')
    
    orphans = alms_cur.fetchall()
    print(f"Orphan charters: {len(orphans)}\n")
    
    created = 0
    linked_existing = 0
    linked_by_account = 0
    failed = 0
    
    for charter_id, reserve_no, charter_date, amount in orphans:
        # Look up LMS reserve to get Account_No
        lms_cur.execute('SELECT Account_No FROM Reserve WHERE Reserve_No = ?', (reserve_no,))
        lms_row = lms_cur.fetchone()
        
        if not lms_row:
            print(f"  ✗ {reserve_no}: Not found in LMS")
            failed += 1
            continue
        
        lms_account_no = lms_row[0]
        
        # Check if we already have a client with this account_number
        if lms_account_no in alms_by_account:
            existing_client_id = alms_by_account[lms_account_no]
            if dry_run:
                print(f"  ✓ {reserve_no}: Link to existing client {existing_client_id} (account {lms_account_no})")
            else:
                alms_cur.execute(
                    'UPDATE charters SET client_id = %s WHERE charter_id = %s',
                    (existing_client_id, charter_id)
                )
                print(f"  ✓ {reserve_no}: Linked to client {existing_client_id}")
            linked_by_account += 1
            continue
        
        # Look up LMS customer Name (not Attention)
        lms_cur.execute('SELECT Name, EMail, Work_Phone, City FROM Customer WHERE Account_No = ?', (lms_account_no,))
        lms_row = lms_cur.fetchone()
        
        if not lms_row or not lms_row[0]:
            print(f"  ✗ {reserve_no}: LMS account {lms_account_no} has no Name")
            failed += 1
            continue
        
        lms_name = lms_row[0]
        lms_email = lms_row[1] or ''
        lms_phone = lms_row[2] or ''
        lms_city = lms_row[3] or ''
        
        # Try to find existing client by name matching
        best_match = None
        best_score = 0.0
        
        for alms_id, alms_name in alms_clients.items():
            score = similarity(lms_name, alms_name)
            if score > best_score:
                best_score = score
                best_match = alms_id
        
        # If good match (>80%), link to existing
        if best_score > 0.8 and best_match:
            if dry_run:
                print(f"  ✓ {reserve_no}: '{lms_name}' → Client {best_match} ({best_score:.1%})")
            else:
                alms_cur.execute(
                    'UPDATE charters SET client_id = %s, client_display_name = %s WHERE charter_id = %s',
                    (best_match, lms_name, charter_id)
                )
                print(f"  ✓ {reserve_no}: Linked to client {best_match}")
            linked_existing += 1
        else:
            # Create new client
            if dry_run:
                print(f"  + {reserve_no}: Create '{lms_name}' (account {lms_account_no})")
            else:
                alms_cur.execute('''
                    INSERT INTO clients (client_name, is_company, account_number, email, primary_phone, city, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    RETURNING client_id
                ''', (lms_name, False, lms_account_no, lms_email, lms_phone, lms_city))
                
                new_client_id = alms_cur.fetchone()[0]
                
                alms_cur.execute(
                    'UPDATE charters SET client_id = %s, client_display_name = %s WHERE charter_id = %s',
                    (new_client_id, lms_name, charter_id)
                )
                
                print(f"  + {reserve_no}: Created client {new_client_id} and linked")
                alms_by_account[lms_account_no] = new_client_id  # Cache for next iteration
            created += 1
    
    print(f"\n{'='*140}")
    print("SUMMARY")
    print(f"{'='*140}")
    
    if dry_run:
        print(f"\nWould process: {len(orphans)} orphan charters")
        print(f"  - Link by account number: {linked_by_account}")
        print(f"  - Link by name match: {linked_existing}")
        print(f"  - Create new clients: {created}")
        print(f"  - Failed: {failed}")
        print(f"\nTo apply changes, run:")
        print(f"  python link_orphan_charters_from_lms.py --write")
    else:
        alms.commit()
        print(f"\n✓ Processed: {len(orphans)} orphan charters")
        print(f"✓ Linked by account: {linked_by_account}")
        print(f"✓ Linked by name: {linked_existing}")
        print(f"✓ Created clients: {created}")
        print(f"✗ Failed: {failed}")
        print(f"\n✓ Changes committed to ALMS database")
    
    alms_cur.close()
    alms.close()
    lms_cur.close()
    lms.close()

if __name__ == '__main__':
    dry_run = '--write' not in sys.argv
    link_orphans(dry_run=dry_run)
