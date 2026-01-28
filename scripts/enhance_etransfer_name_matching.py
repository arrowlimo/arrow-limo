#!/usr/bin/env python3
"""
Enhanced e-transfer name matching by analyzing banking descriptions.

For unmatched e-transfers, extract names from banking descriptions
and fuzzy match to drivers/clients.

Usage:
    python enhance_etransfer_name_matching.py --dry-run
    python enhance_etransfer_name_matching.py --write
"""

import os
import sys
import psycopg2
from difflib import SequenceMatcher
import re

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'almsdata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '***REMOVED***')

DRY_RUN = '--write' not in sys.argv

def get_conn():
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)

def normalize_name(name):
    """Normalize name for comparison."""
    if not name:
        return ""
    
    # Remove common prefixes
    name = re.sub(r'\b(mr|mrs|ms|dr|miss)\b\.?', '', name, flags=re.IGNORECASE)
    
    # Remove punctuation and extra spaces
    name = re.sub(r'[^\w\s]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name.upper()

def fuzzy_match(name1, name2, threshold=0.7):
    """Return True if names match with >= threshold similarity."""
    if not name1 or not name2:
        return False, 0.0
    
    norm1 = normalize_name(name1)
    norm2 = normalize_name(name2)
    
    ratio = SequenceMatcher(None, norm1, norm2).ratio()
    return ratio >= threshold, ratio

def extract_name_from_description(description):
    """Extract recipient/sender name from banking description."""
    if not description:
        return None
    
    # Pattern 1: E-TRANSFER TO/FROM Name
    match = re.search(r'E-TRANSFER\s+(TO|FROM|OUT|IN)\s+([A-Z][A-Za-z\s]+)', description, re.IGNORECASE)
    if match:
        return match.group(2).strip()
    
    # Pattern 2: INTERAC E-TRANSFER - Name
    match = re.search(r'INTERAC.*?-\s*([A-Z][A-Za-z\s]+)', description, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # Pattern 3: Name after TRANSFER
    match = re.search(r'TRANSFER\s+([A-Z][A-Za-z\s]{3,})', description, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    return None

def match_to_drivers(cur, unmatched_out):
    """Match outgoing e-transfers to drivers."""
    
    # Get all driver names
    cur.execute("""
        SELECT employee_id, full_name, first_name, last_name
        FROM employees
        WHERE is_chauffeur = TRUE
        ORDER BY full_name
    """)
    
    drivers = cur.fetchall()
    driver_lookup = {}
    for emp_id, full, first, last in drivers:
        driver_lookup[emp_id] = {
            'full': full,
            'first': first,
            'last': last,
            'names': [full, first, last, f"{first} {last}"]
        }
    
    matched = []
    
    for etrans in unmatched_out:
        etrans_id, tdate, amount, name, banking_id = etrans
        
        if not banking_id:
            continue
        
        # Get banking description
        cur.execute("""
            SELECT description
            FROM banking_transactions
            WHERE transaction_id = %s
        """, (banking_id,))
        
        result = cur.fetchone()
        if not result:
            continue
        
        description = result[0]
        extracted_name = extract_name_from_description(description)
        
        if not extracted_name:
            continue
        
        # Try to match to driver
        best_match = None
        best_ratio = 0.0
        
        for emp_id, driver_info in driver_lookup.items():
            for driver_name in driver_info['names']:
                if not driver_name:
                    continue
                
                is_match, ratio = fuzzy_match(extracted_name, driver_name, threshold=0.7)
                
                if is_match and ratio > best_ratio:
                    best_match = emp_id
                    best_ratio = ratio
        
        if best_match:
            matched.append({
                'etrans_id': etrans_id,
                'extracted_name': extracted_name,
                'driver_id': best_match,
                'driver_name': driver_lookup[best_match]['full'],
                'confidence': best_ratio,
                'date': tdate,
                'amount': amount
            })
    
    return matched

def match_to_clients(cur, unmatched_in):
    """Match incoming e-transfers to clients."""
    
    # Get all client names
    cur.execute("""
        SELECT client_id, client_name
        FROM clients
        WHERE client_name IS NOT NULL
        ORDER BY client_name
    """)
    
    clients = cur.fetchall()
    client_lookup = {cid: cname for cid, cname in clients}
    
    matched = []
    
    for etrans in unmatched_in:
        etrans_id, tdate, amount, name, banking_id = etrans
        
        if not banking_id:
            continue
        
        # Get banking description
        cur.execute("""
            SELECT description
            FROM banking_transactions
            WHERE transaction_id = %s
        """, (banking_id,))
        
        result = cur.fetchone()
        if not result:
            continue
        
        description = result[0]
        extracted_name = extract_name_from_description(description)
        
        if not extracted_name:
            continue
        
        # Try to match to client
        best_match = None
        best_ratio = 0.0
        
        for client_id, client_name in client_lookup.items():
            is_match, ratio = fuzzy_match(extracted_name, client_name, threshold=0.7)
            
            if is_match and ratio > best_ratio:
                best_match = client_id
                best_ratio = ratio
        
        if best_match:
            matched.append({
                'etrans_id': etrans_id,
                'extracted_name': extracted_name,
                'client_id': best_match,
                'client_name': client_lookup[best_match],
                'confidence': best_ratio,
                'date': tdate,
                'amount': amount
            })
    
    return matched

def main():
    print("\n" + "="*80)
    print("ENHANCED E-TRANSFER NAME MATCHING")
    print("="*80)
    print(f"Mode: {'DRY RUN' if DRY_RUN else 'WRITE'}")
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Get unmatched outgoing (potential driver payments)
        print("\n1. Finding unmatched OUTGOING e-transfers...")
        cur.execute("""
            SELECT 
                et.etransfer_id,
                et.transaction_date,
                et.amount,
                et.sender_recipient_name,
                et.banking_transaction_id
            FROM etransfer_transactions et
            WHERE et.direction = 'OUT'
            AND et.banking_transaction_id IS NOT NULL
            AND et.sender_recipient_name IS NULL
            ORDER BY et.amount DESC
        """)
        
        unmatched_out = cur.fetchall()
        print(f"   Found {len(unmatched_out):,} unmatched outgoing with banking links")
        
        # Get unmatched incoming (potential client payments)
        print("\n2. Finding unmatched INCOMING e-transfers...")
        cur.execute("""
            SELECT 
                et.etransfer_id,
                et.transaction_date,
                et.amount,
                et.sender_recipient_name,
                et.banking_transaction_id
            FROM etransfer_transactions et
            WHERE et.direction = 'IN'
            AND et.banking_transaction_id IS NOT NULL
            AND et.sender_recipient_name IS NULL
            ORDER BY et.amount DESC
        """)
        
        unmatched_in = cur.fetchall()
        print(f"   Found {len(unmatched_in):,} unmatched incoming with banking links")
        
        # Match outgoing to drivers
        print("\n3. Matching outgoing to drivers...")
        driver_matches = match_to_drivers(cur, unmatched_out)
        print(f"   Matched {len(driver_matches):,} to drivers")
        
        # Match incoming to clients
        print("\n4. Matching incoming to clients...")
        client_matches = match_to_clients(cur, unmatched_in)
        print(f"   Matched {len(client_matches):,} to clients")
        
        # Show results
        print("\n" + "="*80)
        print("DRIVER PAYMENT MATCHES (Top 20):")
        print("="*80)
        for i, match in enumerate(driver_matches[:20]):
            print(f"{i+1}. {match['date']} | ${match['amount']:>10.2f} | {match['extracted_name']:30} → {match['driver_name']:30} | {match['confidence']:.1%}")
        
        print("\n" + "="*80)
        print("CLIENT PAYMENT MATCHES (Top 20):")
        print("="*80)
        for i, match in enumerate(client_matches[:20]):
            print(f"{i+1}. {match['date']} | ${match['amount']:>10.2f} | {match['extracted_name']:30} → {match['client_name']:30} | {match['confidence']:.1%}")
        
        # Update database if write mode
        if not DRY_RUN:
            print("\n5. Updating database...")
            
            updated = 0
            for match in driver_matches:
                cur.execute("""
                    UPDATE etransfer_transactions
                    SET sender_recipient_name = %s,
                        notes = COALESCE(notes || '; ', '') || 'Matched to driver: ' || %s || ' (confidence: ' || %s || ')'
                    WHERE etransfer_id = %s
                """, (match['extracted_name'], match['driver_name'], f"{match['confidence']:.1%}", match['etrans_id']))
                updated += 1
            
            for match in client_matches:
                cur.execute("""
                    UPDATE etransfer_transactions
                    SET sender_recipient_name = %s,
                        notes = COALESCE(notes || '; ', '') || 'Matched to client: ' || %s || ' (confidence: ' || %s || ')'
                    WHERE etransfer_id = %s
                """, (match['extracted_name'], match['client_name'], f"{match['confidence']:.1%}", match['etrans_id']))
                updated += 1
            
            conn.commit()
            print(f"   Updated {updated:,} e-transfer records")
            print("\n[SUCCESS] Changes committed to database.")
        else:
            conn.rollback()
            print("\n[DRY RUN] No changes saved to database.")
            print("Run with --write to apply changes.")
        
    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()
    
    print("\n" + "="*80)

if __name__ == '__main__':
    main()
