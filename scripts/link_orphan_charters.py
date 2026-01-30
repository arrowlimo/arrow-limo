#!/usr/bin/env python3
"""
Link orphan charters (NULL client_id) to clients by matching LMS account names.
"""

import os
import psycopg2
import pyodbc
import sys
from difflib import SequenceMatcher

DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')
LMS_PATH = r'L:\limo\database_backups\lms2026.mdb'

def similarity(a, b):
    """Calculate string similarity ratio (0.0 to 1.0)"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def link_orphans_to_clients(dry_run=True):
    import pathlib
    
    # Find LMS database
    lms_paths = [
        r'L:\limo\database_backups\lms2026.mdb',
        r'L:\limo\data\lms.mdb',
        r'L:\limo\data\lms2026.mdb'
    ]
    
    LMS_PATH = None
    for path in lms_paths:
        if pathlib.Path(path).exists():
            LMS_PATH = path
            break
    
    if not LMS_PATH:
        print(f"ERROR: Could not find LMS database in: {lms_paths}")
        return
    
    print(f"Using LMS database: {LMS_PATH}")
    """Link orphan charters to clients by LMS account name matching."""
    
    # Connect to ALMS (PostgreSQL)
    alms = psycopg2.connect(
        host='localhost', dbname='almsdata', user='postgres',
        password=DB_PASSWORD
    )
    alms_cur = alms.cursor()
    
    # Connect to LMS (Access)
    lms_conn = pyodbc.connect(
        f'Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    )
    lms_cur = lms_conn.cursor()
    
    print("=" * 140)
    print("LINK ORPHAN CHARTERS TO CLIENTS")
    print("=" * 140)
    print(f"\nMode: {'DRY-RUN' if dry_run else 'WRITE'}\n")
    
    # Get all ALMS clients (for matching)
    alms_cur.execute('''
        SELECT client_id, client_name, company_name
        FROM clients
        WHERE parent_client_id IS NULL
        ORDER BY client_id
    ''')
    
    alms_clients = {}
    for cid, client_name, company_name in alms_cur.fetchall():
        name = company_name or client_name or ''
        if name:
            alms_clients[cid] = name
    
    print(f"ALMS clients loaded: {len(alms_clients)}")
    
    # Get orphan charters
    alms_cur.execute('''
        SELECT charter_id, reserve_number, charter_date
        FROM charters
        WHERE client_id IS NULL
        ORDER BY charter_date DESC
    ''')
    
    orphans = alms_cur.fetchall()
    print(f"Orphan charters: {len(orphans)}\n")
    
    linked = 0
    failed = 0
    
    for charter_id, reserve_no, charter_date in orphans:
        # Look up LMS reserve by reserve number
        lms_cur.execute(
            "SELECT Account_No FROM Reserve WHERE Reserve_No = ?",
            (reserve_no,)
        )
        lms_row = lms_cur.fetchone()
        
        if not lms_row:
            print(f"  ✗ {reserve_no}: Not found in LMS")
            failed += 1
            continue
        
        lms_account_no = lms_row[0]
        
        # Look up LMS customer (account) name
        lms_cur.execute(
            "SELECT Attention FROM Customer WHERE Account_No = ?",
            (lms_account_no,)
        )
        lms_row = lms_cur.fetchone()
        lms_name = lms_row[0] if lms_row else None
        
        if not lms_name:
            print(f"  ✗ {reserve_no}: LMS account {lms_account_no} has no name")
            failed += 1
            continue
        
        # Find best matching ALMS client
        best_match = None
        best_score = 0.0
        
        for alms_id, alms_name in alms_clients.items():
            score = similarity(lms_name, alms_name)
            if score > best_score:
                best_score = score
                best_match = alms_id
        
        # Accept match if similarity > 0.8
        if best_score > 0.8 and best_match:
            if dry_run:
                print(f"  ✓ {reserve_no}: '{lms_name}' → Client {best_match} ({best_score:.1%})")
            else:
                alms_cur.execute(
                    "UPDATE charters SET client_id = %s WHERE charter_id = %s",
                    (best_match, charter_id)
                )
                print(f"  ✓ {reserve_no}: Linked to Client {best_match}")
            linked += 1
        else:
            print(f"  ? {reserve_no}: '{lms_name}' → No good match (best: {best_score:.1%})")
            failed += 1
    
    print(f"\n{'='*140}")
    print(f"SUMMARY: {linked} linked, {failed} failed")
    
    if not dry_run:
        alms.commit()
        print(f"✓ Changes committed to ALMS database")
    else:
        print(f"\nTo apply changes, run:")
        print(f"  python link_orphan_charters.py --write")
    
    alms_cur.close()
    alms.close()
    lms_cur.close()
    lms_conn.close()

if __name__ == '__main__':
    dry_run = '--write' not in sys.argv
    link_orphans_to_clients(dry_run=dry_run)
