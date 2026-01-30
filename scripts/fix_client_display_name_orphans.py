#!/usr/bin/env python3
"""
Fix Client Display Name Orphans

Problem: 47 charters have client_display_name but no client_id (broken FK)
Solution: Match to existing clients or create new client records

Run: python -X utf8 l:\limo\scripts\fix_client_display_name_orphans.py
"""

import psycopg2
import os
from datetime import datetime
from difflib import SequenceMatcher

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REDACTED***')
    )

def similarity_ratio(a, b):
    """Calculate similarity between two strings (0-1)"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("="*80)
    print("FIX CLIENT DISPLAY NAME ORPHANS")
    print("="*80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Step 1: Find orphaned charters
    print("[1/4] Finding charters with client_display_name but no client_id...")
    cur.execute("""
        SELECT charter_id, reserve_number, client_display_name, charter_date
        FROM charters
        WHERE client_display_name IS NOT NULL 
        AND client_display_name != ''
        AND client_id IS NULL
        ORDER BY charter_date DESC
    """)
    orphans = cur.fetchall()
    print(f"   Found: {len(orphans)} orphaned charters\n")
    
    if len(orphans) == 0:
        print("✅ No orphans found. All charters have valid client_id!")
        cur.close()
        conn.close()
        return
    
    # Step 2: Get all existing clients
    print("[2/4] Loading existing clients...")
    cur.execute("""
        SELECT client_id, client_name, company_name, email, primary_phone
        FROM clients
        ORDER BY client_name
    """)
    existing_clients = cur.fetchall()
    print(f"   Loaded: {len(existing_clients)} existing clients\n")
    
    # Step 3: Attempt fuzzy matching
    print("[3/4] Attempting fuzzy matching...")
    matches_found = 0
    no_match = []
    
    for charter_id, reserve_num, display_name, charter_date in orphans:
        best_match = None
        best_score = 0.0
        
        for client_id, client_name, company_name, email, phone in existing_clients:
            # Try matching against client_name
            if client_name:
                score = similarity_ratio(display_name, client_name)
                if score > best_score:
                    best_score = score
                    best_match = (client_id, client_name, 'client_name')
            
            # Try matching against company_name
            if company_name:
                score = similarity_ratio(display_name, company_name)
                if score > best_score:
                    best_score = score
                    best_match = (client_id, company_name, 'company_name')
        
        # If match is good enough (>85% similar), update charter
        if best_score >= 0.85:
            print(f"   ✓ MATCH: '{display_name}' → '{best_match[1]}' (score: {best_score:.2f})")
            cur.execute("""
                UPDATE charters
                SET client_id = %s
                WHERE charter_id = %s
            """, (best_match[0], charter_id))
            matches_found += 1
        else:
            no_match.append((charter_id, reserve_num, display_name, charter_date, best_score if best_match else 0))
    
    conn.commit()
    print(f"\n   Matched: {matches_found} charters to existing clients")
    print(f"   No match: {len(no_match)} charters\n")
    
    # Step 4: Create new clients for no-match cases
    if no_match:
        print("[4/4] Creating new client records for unmatched names...")
        
        # Get unique display names (some charters may have same client)
        unique_names = {}
        for charter_id, reserve_num, display_name, charter_date, score in no_match:
            if display_name not in unique_names:
                unique_names[display_name] = []
            unique_names[display_name].append((charter_id, reserve_num))
        
        created = 0
        for display_name, charter_list in unique_names.items():
            # Generate unique account number
            cur.execute("SELECT MAX(CAST(REGEXP_REPLACE(account_number, '[^0-9]', '', 'g') AS INTEGER)) FROM clients WHERE account_number ~ '^[0-9]+$'")
            max_num = cur.fetchone()[0]
            new_account_num = str((max_num or 0) + 1)
            
            # Create new client
            cur.execute("""
                INSERT INTO clients (account_number, client_name, created_at, notes)
                VALUES (%s, %s, NOW(), %s)
                RETURNING client_id
            """, (new_account_num, display_name, f'Auto-created from charter orphan cleanup on {datetime.now().strftime("%Y-%m-%d")}'))
            new_client_id = cur.fetchone()[0]
            
            # Update all charters with this display name
            for charter_id, reserve_num in charter_list:
                cur.execute("""
                    UPDATE charters
                    SET client_id = %s
                    WHERE charter_id = %s
                """, (new_client_id, charter_id))
            
            print(f"   ✓ Created client '{display_name}' and linked {len(charter_list)} charter(s)")
            created += 1
        
        conn.commit()
        print(f"\n   Created: {created} new client records\n")
    else:
        print("[4/4] No new clients needed - all matched to existing records\n")
    
    # Final verification
    print("="*80)
    print("VERIFICATION")
    print("="*80)
    cur.execute("""
        SELECT COUNT(*)
        FROM charters
        WHERE client_display_name IS NOT NULL 
        AND client_display_name != ''
        AND client_id IS NULL
    """)
    remaining = cur.fetchone()[0]
    
    if remaining == 0:
        print("✅ SUCCESS: All charters now have valid client_id!")
    else:
        print(f"⚠️  WARNING: {remaining} charters still have no client_id")
    
    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
