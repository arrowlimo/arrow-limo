#!/usr/bin/env python3
"""
Analyze all vendor names from receipts and banking_transactions to create
a vendor normalization mapping similar to employee name mapping.

Handles issues like:
- Banking truncation: "PURCHASE1000001234567 CENT" should map to "Centex"
- Location variations: "Esso Red Deer", "Esso Lethbridge" → "Esso"
- Long names: "Phil's Steak and Potato Manufacturing Inc South Side Easy St" → "Phils"
- Transaction prefixes: "POINT OF SALE PURCHASE", "CHEQUE", "DEBIT MEMO"
- Store codes: "#00315", "#4506"
"""

import psycopg2
import os
import re
from collections import defaultdict
from difflib import SequenceMatcher

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def normalize_vendor_base(vendor_name):
    """
    Initial normalization - remove common noise but preserve core identity.
    """
    if not vendor_name:
        return ""
    
    vendor = vendor_name.upper().strip()
    
    # Remove transaction type prefixes
    prefixes = [
        'POINT OF SALE PURCHASE', 'PURCHASE', 'CHEQUE', 'CHQ', 
        'DEBIT MEMO', 'PRE-AUTH', 'CREDIT MEMO', 'WITHDRAWAL',
        'DEPOSIT', 'TRANSFER', 'PAD', 'E-TRANSFER'
    ]
    for prefix in prefixes:
        if vendor.startswith(prefix):
            vendor = vendor[len(prefix):].strip()
    
    # Remove card numbers (4506*********359 format)
    vendor = re.sub(r'\d{4}\*+\d{3,4}', '', vendor)
    
    # Remove purchase reference numbers at start
    vendor = re.sub(r'^\d{10,}', '', vendor)
    
    # Remove store/location codes
    vendor = re.sub(r'#\d+', '', vendor)
    vendor = re.sub(r'\bSTORE\s*\d+\b', '', vendor, flags=re.IGNORECASE)
    vendor = re.sub(r'\bLOCATION\s*\d+\b', '', vendor, flags=re.IGNORECASE)
    
    # Remove common location suffixes
    locations = [
        r'\bRED DEER\b', r'\bLETHBRIDGE\b', r'\bCALGARY\b', r'\bEDMONTON\b',
        r'\bAB\b', r'\bALBERTA\b', r'\bBC\b', r'\bSK\b', r'\bSASKATCHEWAN\b',
        r'\bSOUTH SIDE\b', r'\bNORTH SIDE\b', r'\bEAST\b', r'\bWEST\b',
        r'\bDOWNTOWN\b', r'\bUPTOWN\b'
    ]
    for loc in locations:
        vendor = re.sub(loc, '', vendor, flags=re.IGNORECASE)
    
    # Remove legal entity suffixes
    legal = [
        r'\bINCORPORATED\b', r'\bINC\.?\b', r'\bLIMITED\b', r'\bLTD\.?\b',
        r'\bCORPORATION\b', r'\bCORP\.?\b', r'\bCOMPANY\b', r'\bCO\.?\b',
        r'\bLLC\b', r'\bLLP\b', r'\bGMBH\b'
    ]
    for suffix in legal:
        vendor = re.sub(suffix, '', vendor, flags=re.IGNORECASE)
    
    # Remove possessive markers
    vendor = re.sub(r"['']S?\b", '', vendor)
    
    # Collapse whitespace
    vendor = re.sub(r'\s+', ' ', vendor).strip()
    
    return vendor

def extract_core_vendor_name(vendor_name):
    """
    Extract the core business name from normalized vendor.
    Take first 1-3 significant words.
    """
    if not vendor_name:
        return ""
    
    # Already normalized
    words = vendor_name.split()
    
    # Remove common words that aren't the business name
    stop_words = {'THE', 'A', 'AN', 'AND', 'OR', 'OF', 'FOR', 'AT', 'IN', 'ON'}
    significant_words = [w for w in words if w not in stop_words and len(w) > 1]
    
    if not significant_words:
        return vendor_name
    
    # Take first 1-3 words depending on length
    if len(significant_words[0]) >= 8:
        # Long first word, probably complete name
        return significant_words[0]
    elif len(significant_words) >= 2 and len(significant_words[0]) + len(significant_words[1]) <= 15:
        # Two short words, take both
        return ' '.join(significant_words[:2])
    else:
        # Default to first word
        return significant_words[0]

def get_all_vendors():
    """Get all unique vendor names from receipts and banking."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    vendors = defaultdict(lambda: {'count': 0, 'sources': set(), 'total_amount': 0})
    
    # From receipts
    print("Fetching vendors from receipts...")
    cur.execute("""
        SELECT 
            vendor_name,
            COUNT(*) as count,
            SUM(gross_amount) as total_amount
        FROM receipts
        WHERE vendor_name IS NOT NULL AND vendor_name != ''
        GROUP BY vendor_name
    """)
    
    for vendor, count, amount in cur.fetchall():
        normalized = normalize_vendor_base(vendor)
        if normalized:
            vendors[normalized]['count'] += count
            vendors[normalized]['sources'].add('receipts')
            vendors[normalized]['total_amount'] += float(amount or 0)
            vendors[normalized]['raw_names'] = vendors[normalized].get('raw_names', set())
            vendors[normalized]['raw_names'].add(vendor)
    
    # From banking_transactions (vendor_extracted or description)
    print("Fetching vendors from banking_transactions...")
    cur.execute("""
        SELECT 
            COALESCE(vendor_extracted, description) as vendor,
            COUNT(*) as count,
            SUM(debit_amount) as total_amount
        FROM banking_transactions
        WHERE debit_amount > 0
        AND COALESCE(vendor_extracted, description) IS NOT NULL
        GROUP BY COALESCE(vendor_extracted, description)
    """)
    
    for vendor, count, amount in cur.fetchall():
        normalized = normalize_vendor_base(vendor)
        if normalized:
            vendors[normalized]['count'] += count
            vendors[normalized]['sources'].add('banking')
            vendors[normalized]['total_amount'] += float(amount or 0)
            vendors[normalized]['raw_names'] = vendors[normalized].get('raw_names', set())
            vendors[normalized]['raw_names'].add(vendor)
    
    cur.close()
    conn.close()
    
    return vendors

def group_similar_vendors(vendors):
    """
    Group vendors that are likely the same business using:
    1. Core name extraction
    2. Fuzzy string matching
    3. Common patterns (gas stations, restaurants, etc.)
    """
    
    # Known vendor patterns
    patterns = {
        'CENTEX': ['CENTEX', 'CENT'],
        'ESSO': ['ESSO'],
        'SHELL': ['SHELL', 'CENDALE SHELL'],
        'PETRO': ['PETRO-CAN', 'PETRO CAN', 'PETROCAN'],
        'FAS GAS': ['FAS GAS', 'FASGAS'],
        'HUSKY': ['HUSKY'],
        'CO-OP': ['CO-OP', 'COOP', 'CO OP'],
        'CANADIAN TIRE': ['CANADIAN TIRE', 'CDN TIRE'],
        'TELUS': ['TELUS'],
        'ROGERS': ['ROGERS'],
        'BELL': ['BELL CANADA', 'BELL'],
        'SASKTEL': ['SASKTEL'],
        'STAPLES': ['STAPLES'],
        'TIM HORTONS': ['TIM HORTONS', 'TIMS'],
        'MCDONALDS': ['MCDONALDS', "MCDONALD'S", 'MCDS'],
        'SUBWAY': ['SUBWAY'],
        'A&W': ['A&W', 'A & W'],
        'SOBEYS': ['SOBEYS', "SOBEY'S"],
        'SAFEWAY': ['SAFEWAY'],
        'WALMART': ['WALMART', 'WAL-MART'],
        'HOME DEPOT': ['HOME DEPOT', 'HOMEDEPOT'],
        'RONA': ['RONA'],
        'ROCKY MOUNTAIN': ['ROCKY MOUNTAIN'],
        'PHILS': ['PHIL', 'PHILS', 'PHILLIS'],
    }
    
    # Create mapping
    vendor_groups = defaultdict(list)
    matched = set()
    
    for vendor_name, data in vendors.items():
        core_name = extract_core_vendor_name(vendor_name)
        
        # Check against known patterns
        pattern_matched = False
        for canonical, variations in patterns.items():
            for variation in variations:
                if variation in vendor_name or vendor_name in variation:
                    vendor_groups[canonical].append({
                        'normalized': vendor_name,
                        'core': core_name,
                        'data': data
                    })
                    matched.add(vendor_name)
                    pattern_matched = True
                    break
            if pattern_matched:
                break
        
        # If not matched by pattern, group by core name
        if not pattern_matched:
            vendor_groups[core_name].append({
                'normalized': vendor_name,
                'core': core_name,
                'data': data
            })
    
    return vendor_groups

def fuzzy_match_within_groups(vendor_groups, threshold=0.85):
    """
    Within each group, find vendors that are very similar (likely same business).
    """
    consolidated_groups = {}
    
    for group_name, vendors in vendor_groups.items():
        if len(vendors) == 1:
            consolidated_groups[group_name] = vendors
            continue
        
        # Sort by transaction count (most common first)
        vendors_sorted = sorted(vendors, key=lambda x: x['data']['count'], reverse=True)
        
        # Try to consolidate similar names
        consolidated = []
        used = set()
        
        for i, vendor in enumerate(vendors_sorted):
            if i in used:
                continue
            
            similar = [vendor]
            used.add(i)
            
            for j, other in enumerate(vendors_sorted[i+1:], start=i+1):
                if j in used:
                    continue
                
                ratio = SequenceMatcher(None, vendor['normalized'], other['normalized']).ratio()
                if ratio >= threshold:
                    similar.append(other)
                    used.add(j)
            
            # Merge similar vendors
            if len(similar) > 1:
                # Use most common name as canonical
                merged_data = {
                    'count': sum(v['data']['count'] for v in similar),
                    'total_amount': sum(v['data']['total_amount'] for v in similar),
                    'sources': set().union(*[v['data']['sources'] for v in similar]),
                    'raw_names': set().union(*[v['data']['raw_names'] for v in similar]),
                    'variations': [v['normalized'] for v in similar]
                }
                consolidated.append({
                    'normalized': vendor['normalized'],
                    'core': vendor['core'],
                    'data': merged_data
                })
            else:
                consolidated.append(vendor)
        
        consolidated_groups[group_name] = consolidated
    
    return consolidated_groups

def print_vendor_report(vendor_groups):
    """Print comprehensive vendor report."""
    
    print("\n" + "=" * 120)
    print("VENDOR NORMALIZATION ANALYSIS")
    print("=" * 120)
    
    # Sort groups by total amount
    sorted_groups = sorted(
        vendor_groups.items(),
        key=lambda x: sum(v['data']['total_amount'] for v in x[1]),
        reverse=True
    )
    
    total_vendors = sum(len(vendors) for vendors in vendor_groups.values())
    total_transactions = sum(sum(v['data']['count'] for v in vendors) for vendors in vendor_groups.values())
    total_amount = sum(sum(v['data']['total_amount'] for v in vendors) for vendors in vendor_groups.values())
    
    print(f"\nSUMMARY:")
    print(f"  Total vendor groups: {len(vendor_groups)}")
    print(f"  Total unique vendors: {total_vendors}")
    print(f"  Total transactions: {total_transactions:,}")
    print(f"  Total amount: ${total_amount:,.2f}")
    
    print("\n" + "=" * 120)
    print("TOP 50 VENDORS BY TRANSACTION VOLUME")
    print("=" * 120)
    print(f"{'Canonical Name':<30} {'Txns':<8} {'Amount':<15} {'Sources':<15} {'Variations'}")
    print("-" * 120)
    
    for group_name, vendors in sorted_groups[:50]:
        for vendor in vendors:
            data = vendor['data']
            variations = data.get('variations', [vendor['normalized']])
            sources = ', '.join(sorted(data['sources']))
            
            print(f"{group_name:<30} {data['count']:<8} ${data['total_amount']:<14,.2f} {sources:<15} {len(variations)} variation(s)")
            
            # Show variations if multiple
            if len(variations) > 1:
                for var in variations[:3]:
                    print(f"  └─ {var}")
                if len(variations) > 3:
                    print(f"  └─ ... and {len(variations)-3} more")
            
            # Show sample raw names
            raw_names = list(data.get('raw_names', set()))[:2]
            for raw in raw_names:
                if raw != vendor['normalized']:
                    print(f"     Raw: {raw[:80]}")

def create_vendor_mapping_table(vendor_groups, write=False):
    """Create vendor_name_mapping table similar to employee mapping."""
    
    if not write:
        print("\n" + "=" * 120)
        print("DRY RUN - Would create vendor_name_mapping table")
        print("=" * 120)
        print("Run with --write to create the table")
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "=" * 120)
    print("CREATING vendor_name_mapping TABLE")
    print("=" * 120)
    
    # Drop existing table
    cur.execute("DROP TABLE IF EXISTS vendor_name_mapping CASCADE")
    
    # Create mapping table
    cur.execute("""
        CREATE TABLE vendor_name_mapping (
            id SERIAL PRIMARY KEY,
            raw_vendor_name VARCHAR(500) NOT NULL,
            normalized_vendor_name VARCHAR(200) NOT NULL,
            canonical_vendor_name VARCHAR(200) NOT NULL,
            confidence_score INTEGER DEFAULT 100,
            transaction_count INTEGER DEFAULT 0,
            total_amount DECIMAL(12,2) DEFAULT 0,
            source_systems TEXT[],
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        )
    """)
    
    # Create indexes
    cur.execute("CREATE INDEX idx_vendor_mapping_raw ON vendor_name_mapping(raw_vendor_name)")
    cur.execute("CREATE INDEX idx_vendor_mapping_canonical ON vendor_name_mapping(canonical_vendor_name)")
    
    print("✓ Created table structure and indexes")
    
    # Insert mappings
    inserted = 0
    for group_name, vendors in vendor_groups.items():
        for vendor in vendors:
            data = vendor['data']
            
            # Insert each raw name variation
            for raw_name in data.get('raw_names', set()):
                cur.execute("""
                    INSERT INTO vendor_name_mapping 
                    (raw_vendor_name, normalized_vendor_name, canonical_vendor_name,
                     confidence_score, transaction_count, total_amount, source_systems)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    raw_name,
                    vendor['normalized'],
                    group_name,
                    100,  # High confidence for direct mapping
                    data['count'],
                    data['total_amount'],
                    list(data['sources'])
                ))
                inserted += 1
    
    conn.commit()
    print(f"✓ Inserted {inserted} vendor name mappings")
    
    # Show sample
    cur.execute("""
        SELECT canonical_vendor_name, COUNT(*) as variations,
               SUM(transaction_count) as total_txns,
               SUM(total_amount) as total_amt
        FROM vendor_name_mapping
        GROUP BY canonical_vendor_name
        ORDER BY total_amt DESC
        LIMIT 20
    """)
    
    print("\nTop 20 vendors by amount:")
    print(f"{'Canonical Name':<30} {'Variations':<12} {'Txns':<10} {'Amount'}")
    print("-" * 80)
    for row in cur.fetchall():
        print(f"{row[0]:<30} {row[1]:<12} {row[2]:<10} ${row[3]:,.2f}")
    
    cur.close()
    conn.close()

def main():
    import sys
    write_mode = '--write' in sys.argv
    
    print("Analyzing vendor names from receipts and banking_transactions...")
    
    vendors = get_all_vendors()
    print(f"\nFound {len(vendors)} unique normalized vendor names")
    
    print("\nGrouping similar vendors...")
    vendor_groups = group_similar_vendors(vendors)
    print(f"Created {len(vendor_groups)} vendor groups")
    
    print("\nFuzzy matching within groups...")
    consolidated = fuzzy_match_within_groups(vendor_groups, threshold=0.85)
    print(f"Consolidated to {len(consolidated)} canonical vendors")
    
    print_vendor_report(consolidated)
    
    create_vendor_mapping_table(consolidated, write=write_mode)

if __name__ == '__main__':
    main()
