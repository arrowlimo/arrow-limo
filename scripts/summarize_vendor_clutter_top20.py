"""
Summarize top vendor clutter groups for user confirmation
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
    """Normalize vendor name for grouping."""
    if not vendor_name:
        return ""
    
    normalized = vendor_name.upper().strip()
    normalized = re.sub(r'^(THE|A|AN)\s+', '', normalized)
    normalized = re.sub(r'\s+(LTD|LIMITED|INC|INCORPORATED|CORP|CORPORATION|LLC|CO|COMPANY)\.?$', '', normalized)
    normalized = re.sub(r'\s+\(.*?\)$', '', normalized)
    normalized = re.sub(r'\s+(RED DEER|LETHBRIDGE|CALGARY|EDMONTON|TORONTO|VANCOUVER|OTTAWA|AB|BC|SK|ON|CANADA)\s*', '', normalized)
    normalized = re.sub(r'#\d+', '', normalized)
    normalized = re.sub(r'\d{4}\*+\d{3}', '', normalized)
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
    """Get all unique vendors from receipts."""
    conn = get_db_connection()
    cur = conn.cursor()
    
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
    """Summarize top vendor clutter groups."""
    print("\n" + "="*80)
    print("TOP 20 VENDOR CLUTTER GROUPS - FOR YOUR CONFIRMATION")
    print("="*80 + "\n")
    
    vendors = get_vendor_variations()
    vendor_list = list(vendors.keys())
    
    print(f"Total unique vendor names: {len(vendor_list)}")
    print(f"Total receipts: {sum(vendors.values())}\n")
    
    # Group vendors
    groups = group_similar_vendors(vendor_list, threshold=0.75)
    
    # Filter to only groups with multiple vendors
    cluttered_groups = [g for g in groups if len(g) > 1]
    
    print(f"Found {len(cluttered_groups)} vendor groups with variations\n")
    print("="*80)
    print("TOP 20 GROUPS BY RECEIPTS COUNT")
    print("="*80 + "\n")
    
    # Sort by total receipts and show top 20
    sorted_groups = sorted(cluttered_groups, key=lambda x: sum(vendors[v] for v in x), reverse=True)
    
    for idx, group in enumerate(sorted_groups[:20], 1):
        total_receipts = sum(vendors[v] for v in group)
        most_common = max(group, key=lambda v: vendors[v])
        
        print(f"\n{idx}. CONSOLIDATE TO: '{most_common}'")
        print(f"   Total receipts affected: {total_receipts}")
        print(f"   Number of variations: {len(group)}")
        print(f"\n   Variations:")
        
        # Show first 5 variations
        for vendor in sorted(group, key=lambda v: vendors[v], reverse=True)[:5]:
            if vendor != most_common:
                print(f"     • '{vendor}' ({vendors[vendor]})")
        
        if len(group) > 5:
            remaining = len(group) - 5
            print(f"     + {remaining} more variations...")
        
        print(f"   [APPROVE / REJECT / MODIFY]")

if __name__ == '__main__':
    main()
