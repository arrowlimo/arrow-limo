"""
Analyze receipt vendor names for clutter and grouping
Identify patterns without QuickBooks entries (no X, DD, dd prefixes)
Use fuzzy matching to group similar vendors
"""

import psycopg2
from difflib import SequenceMatcher
from collections import defaultdict
import os
import re

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REDACTED***')
    )

def normalize_vendor_for_clustering(vendor_name):
    """Normalize vendor name for grouping - keep original for display."""
    if not vendor_name:
        return ""
    
    normalized = vendor_name.upper().strip()
    
    # Remove common prefixes/suffixes
    normalized = re.sub(r'^(THE|A|AN)\s+', '', normalized)
    normalized = re.sub(r'\s+(LTD|LIMITED|INC|INCORPORATED|CORP|CORPORATION|LLC|CO|COMPANY)\.?$', '', normalized)
    normalized = re.sub(r'\s+\(.*?\)$', '', normalized)  # Remove parenthetical info
    
    # Remove location codes and suffixes
    normalized = re.sub(r'\s+(RED DEER|LETHBRIDGE|CALGARY|EDMONTON|TORONTO|VANCOUVER|OTTAWA|AB|AB|BC|SK|ON|CANADA)\s*', '', normalized)
    
    # Remove location numbers
    normalized = re.sub(r'#\d+', '', normalized)
    normalized = re.sub(r'\d{4}\*+\d{3}', '', normalized)  # Card numbers
    
    # Collapse whitespace
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized

def fuzzy_match(str1, str2, threshold=0.7):
    """Calculate fuzzy match ratio."""
    if not str1 or not str2:
        return 0.0
    return SequenceMatcher(None, str1.upper(), str2.upper()).ratio()

def group_similar_vendors(vendor_list, threshold=0.75):
    """Group vendors by fuzzy matching."""
    if not vendor_list:
        return []
    
    groups = []
    used = set()
    
    for i, vendor1 in enumerate(vendor_list):
        if i in used:
            continue
        
        group = [vendor1]
        used.add(i)
        
        norm1 = normalize_vendor_for_clustering(vendor1)
        
        for j, vendor2 in enumerate(vendor_list):
            if j <= i or j in used:
                continue
            
            norm2 = normalize_vendor_for_clustering(vendor2)
            
            if norm1 and norm2 and fuzzy_match(norm1, norm2, threshold) >= threshold:
                group.append(vendor2)
                used.add(j)
        
        if len(group) > 0:
            groups.append(sorted(list(set(group))))
    
    return groups

def get_vendor_variations():
    """Get all unique vendors from receipts (excluding QB entries)."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get all unique vendors, excluding QB entries (those starting with X, DD, dd patterns)
    cur.execute("""
        SELECT DISTINCT vendor_name, COUNT(*) as count
        FROM receipts
        WHERE vendor_name IS NOT NULL 
        AND vendor_name != ''
        AND vendor_name NOT LIKE 'X %'
        AND vendor_name NOT LIKE 'DD %'
        AND vendor_name NOT LIKE 'dd %'
        AND vendor_name NOT LIKE 'CHQ %'
        AND vendor_name NOT LIKE 'CHEQUE %'
        AND vendor_name NOT LIKE 'PURCHASE%'
        GROUP BY vendor_name
        ORDER BY count DESC
    """)
    
    vendors = {}
    for row in cur.fetchall():
        vendors[row[0]] = row[1]
    
    cur.close()
    conn.close()
    
    return vendors

def main():
    """Analyze and group vendor names."""
    print("\n" + "="*80)
    print("RECEIPT VENDOR CLUTTER ANALYSIS")
    print("Grouping Similar Vendors for Cleanup")
    print("="*80 + "\n")
    
    vendors = get_vendor_variations()
    vendor_list = list(vendors.keys())
    
    print(f"Total unique vendor names: {len(vendor_list)}")
    print(f"Total receipts: {sum(vendors.values())}\n")
    
    # Group vendors
    print("Analyzing vendor similarity (75% fuzzy match threshold)...\n")
    groups = group_similar_vendors(vendor_list, threshold=0.75)
    
    # Filter to only groups with multiple vendors (clutter)
    cluttered_groups = [g for g in groups if len(g) > 1]
    
    print(f"Found {len(cluttered_groups)} vendor groups with variations needing cleanup\n")
    print("="*80)
    print("VENDOR GROUPS - Review and Confirm Prior to Cleanup")
    print("="*80 + "\n")
    
    group_num = 1
    for group in sorted(cluttered_groups, key=lambda grp: sum(vendors[v] for v in grp), reverse=True):
        total_receipts = sum(vendors[v] for v in group)
        
        print(f"\n{'-'*80}")
        print(f"GROUP {group_num}: ({total_receipts} total receipts)")
        print(f"{'-'*80}")
        
        # Find the most common vendor in the group (recommended cleanup target)
        most_common = max(group, key=lambda v: vendors[v])
        
        print(f"\nRecommended standard name: '{most_common}'")
        print(f"Receipts: {vendors[most_common]}\n")
        
        print("Variations to consolidate into standard name:")
        for vendor in sorted(group, key=lambda v: vendors[v], reverse=True):
            if vendor != most_common:
                print(f"  • '{vendor}' ({vendors[vendor]} receipts)")
        
        group_num += 1
    
    # Also show single vendors with obvious clutter in name
    print(f"\n\n{'='*80}")
    print("STANDALONE VENDORS - Potential Name Cleanup (no consolidation needed)")
    print("="*80 + "\n")
    
    clutter_patterns = [
        (r'.*\s{2,}.*', 'Double spaces'),
        (r'.*\([^)]*\).*', 'Parenthetical info'),
        (r'.*\d{4}\*+\d{3}.*', 'Card number embedded'),
        (r'.*#\d{3,}.*', 'Store/location code'),
        (r'.*\s(RED DEER|LETHBRIDGE|CALGARY|EDMONTON)\s.*', 'City name in vendor'),
    ]
    
    standalone_with_clutter = []
    for vendor in vendor_list:
        if vendors[vendor] >= 3:  # Only vendors with 3+ receipts
            for pattern, reason in clutter_patterns:
                if re.search(pattern, vendor):
                    standalone_with_clutter.append((vendor, vendors[vendor], reason))
                    break
    
    if standalone_with_clutter:
        for i, (vendor, count, reason) in enumerate(sorted(standalone_with_clutter, key=lambda x: x[1], reverse=True), 1):
            print(f"\n{i}. '{vendor}'")
            print(f"   Issue: {reason}")
            print(f"   Receipts: {count}")
            
            # Suggest cleanup
            cleaned = normalize_vendor_for_clustering(vendor)
            if cleaned != vendor.upper():
                print(f"   Suggested cleanup: '{cleaned}'")
    else:
        print("No standalone vendors with obvious clutter found.")
    
    # Summary statistics
    print(f"\n\n{'='*80}")
    print("SUMMARY")
    print("="*80)
    print(f"Total unique vendors: {len(vendor_list)}")
    print(f"Vendor groups with variations: {len(cluttered_groups)}")
    total_affected = sum(sum(vendors[v] for v in g) for g in cluttered_groups)
    print(f"Receipts affected by grouping: {total_affected}")
    print(f"Receipts from standalone vendors: {sum(vendors.values()) - total_affected}")
    print("\n" + "="*80 + "\n")

if __name__ == '__main__':
    main()
