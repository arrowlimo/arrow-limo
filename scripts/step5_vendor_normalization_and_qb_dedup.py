#!/usr/bin/env python3
"""
VENDOR NORMALIZATION & QB DEDUPLICATION
1. Extract clean vendor names from Scotia banking
2. Find QB receipts with fuzzy-matched vendors + same date+amount
3. Deduplicate QB using normalized names
4. Cascade normalization to all sources
"""

import os
from difflib import SequenceMatcher
from collections import defaultdict

import pandas as pd
import psycopg2

DB_SETTINGS = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "almsdata"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "***REMOVED***"),
}

def normalize_vendor_name(name):
    """Normalize vendor name for comparison."""
    if not name:
        return ""
    name = str(name).upper().strip()
    # Remove common suffixes
    for suffix in [' INC', ' LTD', ' LTD.', ' CORP', ' CORP.', ' CO.', ' & CO.', ' LLC', ' CORP.']:
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()
    # Remove punctuation
    name = name.replace('.', '').replace(',', '').replace('&', 'AND')
    # Collapse whitespace
    name = ' '.join(name.split())
    return name

def fuzzy_match(name1, name2, threshold=0.85):
    """Fuzzy match two vendor names."""
    n1 = normalize_vendor_name(name1)
    n2 = normalize_vendor_name(name2)
    
    if not n1 or not n2:
        return False
    
    # Exact match after normalization
    if n1 == n2:
        return True
    
    # Sequence matcher ratio
    ratio = SequenceMatcher(None, n1, n2).ratio()
    return ratio >= threshold

def extract_scotia_vendors():
    """Extract clean vendor names from Scotia banking."""
    print("\n" + "="*80)
    print("STEP 1: EXTRACT VENDOR NAMES FROM SCOTIA BANKING (Cleanest Source)")
    print("="*80)
    
    conn = psycopg2.connect(**DB_SETTINGS)
    cur = conn.cursor()
    
    try:
        # Get Scotia descriptions (most manual cleanup)
        cur.execute("""
            SELECT DISTINCT description, COUNT(*) as cnt
            FROM banking_transactions
            WHERE account_number = '903990106011'
              AND EXTRACT(YEAR FROM transaction_date) = 2012
              AND debit_amount > 0
            GROUP BY description
            ORDER BY cnt DESC
        """)
        
        scotia_vendors = {}
        for desc, cnt in cur.fetchall():
            if desc:
                vendor = normalize_vendor_name(desc)
                if vendor and len(vendor) > 3:
                    scotia_vendors[vendor] = {
                        'original': desc,
                        'count': cnt,
                        'source': 'Scotia'
                    }
        
        print(f"\n[OK] Extracted {len(scotia_vendors)} unique Scotia vendors")
        print("\nTop 20 Scotia vendors:")
        for vendor, info in sorted(scotia_vendors.items(), key=lambda x: x[1]['count'], reverse=True)[:20]:
            print(f"  {vendor:40s} | {info['count']:3d} | {info['original'][:50]}")
        
        return scotia_vendors
    
    finally:
        cur.close()
        conn.close()

def find_qb_duplicates_by_vendor_and_amount(scotia_vendors, dry_run=True):
    """Find QB receipts matching Scotia vendors by fuzzy name + date+amount."""
    print("\n" + "="*80)
    print("STEP 2: FIND QB RECEIPTS MATCHING SCOTIA VENDORS (Fuzzy Name + Date + Amount)")
    print("="*80)
    print(f"Mode: {'DRY-RUN' if dry_run else 'WRITE'}\n")
    
    conn = psycopg2.connect(**DB_SETTINGS)
    cur = conn.cursor()
    
    try:
        # Get all QB receipts (source='quickbooks' or created_from_banking=false for CIBC)
        cur.execute("""
            SELECT receipt_id, receipt_date, vendor_name, gross_amount, category, description
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = 2012
              AND (category LIKE '%quickbooks%' OR mapped_bank_account_id = 1)
            ORDER BY receipt_date, vendor_name
        """)
        
        qb_receipts = cur.fetchall()
        print(f"Analyzing {len(qb_receipts)} QB/CIBC receipts for vendor matching...\n")
        
        matches = []
        no_matches = defaultdict(int)
        
        for receipt_id, date, vendor, amount, category, desc in qb_receipts:
            if not vendor:
                continue
            
            vendor_norm = normalize_vendor_name(vendor)
            
            # Check if this QB vendor matches any Scotia vendor
            best_match = None
            best_score = 0
            
            for scotia_vendor, scotia_info in scotia_vendors.items():
                if fuzzy_match(vendor_norm, scotia_vendor, threshold=0.80):
                    score = SequenceMatcher(None, vendor_norm, scotia_vendor).ratio()
                    if score > best_score:
                        best_match = scotia_vendor
                        best_score = score
            
            if best_match:
                # Check for date+amount matches in Scotia
                cur.execute("""
                    SELECT transaction_id, transaction_date, description, debit_amount
                    FROM banking_transactions
                    WHERE account_number = '903990106011'
                      AND EXTRACT(YEAR FROM transaction_date) = 2012
                      AND transaction_date = %s
                      AND debit_amount = %s
                    LIMIT 1
                """, (date, amount))
                
                scotia_match = cur.fetchone()
                
                if scotia_match:
                    scotia_tx_id, scotia_date, scotia_desc, scotia_amt = scotia_match
                    matches.append({
                        'qb_receipt_id': receipt_id,
                        'qb_vendor': vendor,
                        'qb_vendor_norm': vendor_norm,
                        'scotia_vendor': scotia_desc,
                        'scotia_vendor_norm': best_match,
                        'date': date,
                        'amount': amount,
                        'score': best_score,
                        'suggested_vendor': best_match.title(),
                    })
            else:
                no_matches[vendor_norm] += 1
        
        print(f"Found {len(matches)} QB receipts matching Scotia vendors by fuzzy name + date+amount")
        
        if matches:
            print("\nTop 20 QB-Scotia matches (by confidence score):")
            for match in sorted(matches, key=lambda x: x['score'], reverse=True)[:20]:
                print(f"  {match['date']} | ${match['amount']:>10.2f}")
                print(f"    QB: {match['qb_vendor'][:40]:40s} -> {match['suggested_vendor']}")
                print(f"    Score: {match['score']:.2%}")
        
        print(f"\nQB vendors with NO Scotia match: {len(no_matches)}")
        print("Top 20 unmatched QB vendors:")
        for vendor, cnt in sorted(no_matches.items(), key=lambda x: x[1], reverse=True)[:20]:
            print(f"  {vendor:40s} | {cnt:3d} receipts")
        
        return matches
    
    finally:
        cur.close()
        conn.close()

def deduplicate_qb_by_vendor_amount(matches, dry_run=True):
    """Deduplicate QB receipts: keep one per vendor+date+amount, merge descriptions."""
    print("\n" + "="*80)
    print("STEP 3: DEDUPLICATE QB RECEIPTS (Keep 1 per vendor+date+amount)")
    print("="*80)
    print(f"Mode: {'DRY-RUN' if dry_run else 'WRITE'}\n")
    
    conn = psycopg2.connect(**DB_SETTINGS)
    cur = conn.cursor()
    
    try:
        # Group QB receipts by date+normalized_vendor+amount
        cur.execute("""
            SELECT receipt_date, UPPER(vendor_name), gross_amount, 
                   COUNT(*) as cnt, ARRAY_AGG(receipt_id ORDER BY receipt_id) as ids
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = 2012
              AND (category LIKE '%quickbooks%' OR mapped_bank_account_id = 1)
            GROUP BY receipt_date, UPPER(vendor_name), gross_amount
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC
        """)
        
        qb_dups = cur.fetchall()
        print(f"Found {len(qb_dups)} QB duplicate groups (date+vendor+amount)")
        
        total_to_delete = sum(row[3] - 1 for row in qb_dups)
        print(f"Total receipts to remove: {total_to_delete}\n")
        
        if qb_dups:
            print("Top 20 QB duplicate groups:")
            for date, vendor, amount, cnt, ids in qb_dups[:20]:
                print(f"  {date} | {vendor[:30]:30s} | ${amount:>10.2f} | {cnt} rows")
                print(f"    Keep ID {ids[0]}, remove {cnt-1}: {ids[1:]}")
        
        if not dry_run and qb_dups:
            ids_to_delete = []
            for date, vendor, amount, cnt, ids in qb_dups:
                # Keep first, delete rest
                ids_to_delete.extend(ids[1:])
            
            if ids_to_delete:
                # Delete ledger entries
                cur.execute("""
                    DELETE FROM banking_receipt_matching_ledger
                    WHERE receipt_id = ANY(%s)
                """, (ids_to_delete,))
                ledger_del = cur.rowcount
                
                # Delete banking links (if any direct FK)
                cur.execute("""
                    DELETE FROM banking_transactions
                    WHERE receipt_id = ANY(%s)
                """, (ids_to_delete,))
                banking_del = cur.rowcount
                
                # Delete receipts
                cur.execute("""
                    DELETE FROM receipts
                    WHERE receipt_id = ANY(%s)
                """, (ids_to_delete,))
                receipt_del = cur.rowcount
                
                conn.commit()
                print(f"\n[OK] Removed {receipt_del} QB duplicate receipts, {ledger_del} ledger entries, {banking_del} banking links")
        else:
            print(f"\n[DRY-RUN] Would remove {total_to_delete} QB duplicate receipts")
        
        return len(qb_dups)
    
    finally:
        cur.close()
        conn.close()

def normalize_vendor_names_in_db(dry_run=True):
    """Update vendor names to normalized versions."""
    print("\n" + "="*80)
    print("STEP 4: NORMALIZE VENDOR NAMES ACROSS ALL RECEIPTS")
    print("="*80)
    print(f"Mode: {'DRY-RUN' if dry_run else 'WRITE'}\n")
    
    conn = psycopg2.connect(**DB_SETTINGS)
    cur = conn.cursor()
    
    try:
        # Get all distinct vendors for 2012
        cur.execute("""
            SELECT vendor_name, COUNT(*) as cnt
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = 2012
              AND vendor_name IS NOT NULL
            GROUP BY vendor_name
            ORDER BY cnt DESC
        """)
        
        vendors = cur.fetchall()
        print(f"Processing {len(vendors)} distinct vendor names...\n")
        
        updates = 0
        
        for vendor, cnt in vendors:
            vendor_norm = normalize_vendor_name(vendor)
            
            # Only update if normalization changed the name
            if vendor_norm and vendor_norm.title() != vendor:
                if not dry_run:
                    cur.execute("""
                        UPDATE receipts
                        SET vendor_name = %s
                        WHERE vendor_name = %s AND EXTRACT(YEAR FROM receipt_date) = 2012
                    """, (vendor_norm.title(), vendor))
                    
                    if cur.rowcount > 0:
                        updates += 1
                        if updates <= 20:
                            print(f"  {vendor[:35]:35s} -> {vendor_norm.title()[:35]:35s} | {cnt:3d} rows")
                else:
                    updates += 1
                    if updates <= 20:
                        print(f"  [PREVIEW] {vendor[:35]:35s} -> {vendor_norm.title()[:35]:35s} | {cnt:3d} rows")
        
        if not dry_run:
            conn.commit()
            print(f"\n[OK] Updated {updates} vendor names across receipts")
        else:
            print(f"\n[DRY-RUN] Would update {updates} vendor names")
        
        return updates
    
    finally:
        cur.close()
        conn.close()

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Vendor normalization & QB deduplication')
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing')
    parser.add_argument('--write', action='store_true', help='Apply changes to DB')
    args = parser.parse_args()
    
    if not args.write:
        args.dry_run = True
    
    print("\n" + "="*80)
    print("VENDOR NORMALIZATION & QB DEDUPLICATION")
    print("="*80)
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'WRITE'}")
    
    # Step 1: Extract Scotia vendors
    scotia_vendors = extract_scotia_vendors()
    
    # Step 2: Find QB matches
    matches = find_qb_duplicates_by_vendor_and_amount(scotia_vendors, dry_run=args.dry_run)
    
    # Step 3: Dedup QB
    dup_groups = deduplicate_qb_by_vendor_amount(matches, dry_run=args.dry_run)
    
    # Step 4: Normalize all vendor names
    normalized_count = normalize_vendor_names_in_db(dry_run=args.dry_run)
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Scotia vendors extracted: {len(scotia_vendors)}")
    print(f"QB-Scotia matches found: {len(matches)}")
    print(f"QB duplicate groups found: {dup_groups}")
    print(f"Vendor names normalized: {normalized_count}")
    print("="*80)

if __name__ == '__main__':
    main()
