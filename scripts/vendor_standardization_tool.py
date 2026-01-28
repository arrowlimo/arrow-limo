#!/usr/bin/env python3
"""
Vendor Standardization Tool - Find and standardize vendor name variations

This tool scans all vendor names from receipts and banking_transactions,
uses fuzzy matching to detect duplicates, and helps standardize them to
canonical names.

Usage:
    python vendor_standardization_tool.py scan              # Scan and show variations
    python vendor_standardization_tool.py analyze           # Analyze duplicates
    python vendor_standardization_tool.py standardize       # Interactive standardization
    python vendor_standardization_tool.py apply FILE        # Apply standardization from CSV
    python vendor_standardization_tool.py report            # Generate report
"""

import sys
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from difflib import SequenceMatcher
from collections import defaultdict
import csv
from datetime import datetime
import re

# Database connection
DB_CONFIG = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres',
    'password': os.environ.get('DB_PASSWORD', '***REMOVED***')
}


def normalize_vendor_name(name):
    """Normalize vendor name for comparison"""
    if not name:
        return ""
    # Convert to uppercase
    name = str(name).upper().strip()
    # Remove common suffixes
    name = re.sub(r'\s+(LTD|LIMITED|INC|CORP|CORPORATION|CO|COMPANY)\s*$', '', name)
    # Remove extra whitespace
    name = re.sub(r'\s+', ' ', name)
    # Remove special characters
    name = re.sub(r'[^\w\s-]', '', name)
    return name.strip()


def similarity_ratio(str1, str2):
    """Calculate similarity ratio between two strings (0.0 to 1.0)"""
    if not str1 or not str2:
        return 0.0
    return SequenceMatcher(None, str1, str2).ratio()


def scan_vendor_names(conn):
    """Scan all vendor names from database"""
    print("=" * 100)
    print("SCANNING VENDOR NAMES FROM ALL SOURCES")
    print("=" * 100)
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Scan from receipts
    print("\n1. Scanning receipts.vendor_name...")
    cur.execute("""
        SELECT DISTINCT vendor_name, canonical_vendor, COUNT(*) as count
        FROM receipts
        WHERE vendor_name IS NOT NULL AND vendor_name != ''
        GROUP BY vendor_name, canonical_vendor
        ORDER BY count DESC
    """)
    receipt_vendors = cur.fetchall()
    print(f"   Found {len(receipt_vendors)} unique vendor names in receipts")
    
    # Scan from receipts canonical
    print("\n2. Scanning receipts.canonical_vendor...")
    cur.execute("""
        SELECT DISTINCT canonical_vendor, COUNT(*) as count
        FROM receipts
        WHERE canonical_vendor IS NOT NULL AND canonical_vendor != ''
        GROUP BY canonical_vendor
        ORDER BY count DESC
    """)
    canonical_vendors = cur.fetchall()
    print(f"   Found {len(canonical_vendors)} unique canonical vendor names")
    
    # Scan from banking_transactions
    print("\n3. Scanning banking_transactions.vendor_extracted...")
    cur.execute("""
        SELECT DISTINCT vendor_extracted, COUNT(*) as count
        FROM banking_transactions
        WHERE vendor_extracted IS NOT NULL 
          AND vendor_extracted != ''
          AND vendor_extracted NOT IN ('Customer', 'Unknown', 'Deposit', 'Transfer')
        GROUP BY vendor_extracted
        ORDER BY count DESC
    """)
    banking_vendors = cur.fetchall()
    print(f"   Found {len(banking_vendors)} unique vendor names in banking")
    
    # Combine all vendor names
    all_vendors = {}
    
    for r in receipt_vendors:
        vendor = r['vendor_name']
        normalized = normalize_vendor_name(vendor)
        if normalized not in all_vendors:
            all_vendors[normalized] = {
                'original_names': set(),
                'canonical': r['canonical_vendor'],
                'total_count': 0,
                'sources': set()
            }
        all_vendors[normalized]['original_names'].add(vendor)
        all_vendors[normalized]['total_count'] += r['count']
        all_vendors[normalized]['sources'].add('receipts.vendor_name')
    
    for r in canonical_vendors:
        vendor = r['canonical_vendor']
        normalized = normalize_vendor_name(vendor)
        if normalized not in all_vendors:
            all_vendors[normalized] = {
                'original_names': set(),
                'canonical': vendor,
                'total_count': 0,
                'sources': set()
            }
        all_vendors[normalized]['original_names'].add(vendor)
        all_vendors[normalized]['total_count'] += r['count']
        all_vendors[normalized]['sources'].add('receipts.canonical_vendor')
    
    for r in banking_vendors:
        vendor = r['vendor_extracted']
        normalized = normalize_vendor_name(vendor)
        if normalized not in all_vendors:
            all_vendors[normalized] = {
                'original_names': set(),
                'canonical': None,
                'total_count': 0,
                'sources': set()
            }
        all_vendors[normalized]['original_names'].add(vendor)
        all_vendors[normalized]['total_count'] += r['count']
        all_vendors[normalized]['sources'].add('banking_transactions')
    
    print(f"\n" + "=" * 100)
    print(f"TOTAL: {len(all_vendors)} unique normalized vendor names")
    print("=" * 100)
    
    return all_vendors


def find_duplicates(all_vendors, threshold=0.85):
    """Find potential duplicate vendor names using fuzzy matching"""
    print("\n" + "=" * 100)
    print(f"FINDING DUPLICATES (similarity threshold: {threshold:.0%})")
    print("=" * 100)
    
    vendor_list = sorted(all_vendors.keys())
    duplicate_groups = []
    processed = set()
    
    for i, vendor1 in enumerate(vendor_list):
        if vendor1 in processed:
            continue
        
        group = {vendor1}
        
        for j, vendor2 in enumerate(vendor_list[i+1:], i+1):
            if vendor2 in processed:
                continue
            
            ratio = similarity_ratio(vendor1, vendor2)
            if ratio >= threshold:
                group.add(vendor2)
                processed.add(vendor2)
        
        if len(group) > 1:
            duplicate_groups.append(group)
            processed.add(vendor1)
    
    # Sort groups by total transaction count
    sorted_groups = []
    for group in duplicate_groups:
        total_count = sum(all_vendors[v]['total_count'] for v in group)
        sorted_groups.append((total_count, group))
    
    sorted_groups.sort(reverse=True)
    
    print(f"\nFound {len(sorted_groups)} groups with potential duplicates:\n")
    
    for idx, (total_count, group) in enumerate(sorted_groups[:50], 1):  # Show top 50
        print(f"\n{idx}. GROUP (Total: {total_count:,} transactions)")
        print("   " + "-" * 90)
        for vendor in sorted(group):
            info = all_vendors[vendor]
            original_names = ', '.join(sorted(info['original_names']))
            canonical = info.get('canonical') or 'NO CANONICAL'
            sources = ', '.join(sorted(info['sources']))
            print(f"   • {vendor:<40} | Original: {original_names[:50]:<50}")
            print(f"     Count: {info['total_count']:>6,} | Canonical: {canonical:<30} | Sources: {sources}")
    
    if len(sorted_groups) > 50:
        print(f"\n... and {len(sorted_groups) - 50} more groups")
    
    return sorted_groups


def interactive_standardization(conn, all_vendors, duplicate_groups):
    """Interactive session to standardize vendor names"""
    print("\n" + "=" * 100)
    print("INTERACTIVE VENDOR STANDARDIZATION")
    print("=" * 100)
    print("\nFor each group, select the canonical name to use.")
    print("Press Enter to skip a group, or type a new canonical name.")
    print()
    
    standardizations = []
    
    for idx, (total_count, group) in enumerate(duplicate_groups, 1):
        print(f"\n{idx}/{len(duplicate_groups)} - GROUP ({total_count:,} transactions)")
        print("=" * 100)
        
        # Show all variations
        variations = []
        for vendor_norm in sorted(group):
            info = all_vendors[vendor_norm]
            for original in info['original_names']:
                variations.append((original, info['total_count'], info.get('canonical')))
        
        # Sort by count
        variations.sort(key=lambda x: x[1], reverse=True)
        
        # Display variations
        for i, (name, count, canonical) in enumerate(variations, 1):
            marker = "★" if canonical else " "
            print(f"  {marker} {i}. {name:<50} ({count:>6,} uses) {f'[Canon: {canonical}]' if canonical else ''}")
        
        # Suggest canonical name (most common or existing canonical)
        suggested = None
        for name, count, canonical in variations:
            if canonical:
                suggested = canonical
                break
        if not suggested:
            suggested = variations[0][0]  # Most common
        
        print(f"\nSuggested canonical name: {suggested}")
        choice = input("Enter canonical name (or number 1-{}, or Enter to skip, 'q' to quit): ".format(len(variations)))
        
        if choice.lower() == 'q':
            break
        
        if not choice.strip():
            print("  ⏩ Skipped")
            continue
        
        # Parse choice
        canonical_name = None
        if choice.isdigit() and 1 <= int(choice) <= len(variations):
            canonical_name = variations[int(choice) - 1][0]
        else:
            canonical_name = choice.strip().upper()
        
        # Add standardization
        for name, count, _ in variations:
            standardizations.append({
                'original_name': name,
                'canonical_name': canonical_name,
                'transaction_count': count
            })
        
        print(f"  ✓ Will standardize {len(variations)} names to: {canonical_name}")
    
    return standardizations


def apply_standardizations(conn, standardizations, dry_run=True):
    """Apply vendor standardizations to database"""
    print("\n" + "=" * 100)
    print("APPLYING STANDARDIZATIONS" + (" (DRY RUN)" if dry_run else ""))
    print("=" * 100)
    
    if not standardizations:
        print("No standardizations to apply")
        return
    
    cur = conn.cursor()
    
    # Group by canonical name
    by_canonical = defaultdict(list)
    for std in standardizations:
        by_canonical[std['canonical_name']].append(std['original_name'])
    
    print(f"\nWill create/update {len(by_canonical)} canonical vendor records")
    print(f"Will standardize {len(standardizations)} vendor name variations\n")
    
    for canonical, originals in sorted(by_canonical.items()):
        print(f"\n📌 {canonical}")
        print(f"   Variations: {', '.join(sorted(originals))}")
        
        if not dry_run:
            # Update receipts
            for original in originals:
                cur.execute("""
                    UPDATE receipts
                    SET canonical_vendor = %s
                    WHERE vendor_name = %s OR canonical_vendor = %s
                """, (canonical, original, original))
                if cur.rowcount > 0:
                    print(f"   ✓ Updated {cur.rowcount} receipts for '{original}'")
    
    if dry_run:
        print("\n" + "=" * 100)
        print("DRY RUN COMPLETE - No changes were made to the database")
        print("Run with --apply flag to actually apply these changes")
        print("=" * 100)
    else:
        conn.commit()
        print("\n" + "=" * 100)
        print("STANDARDIZATIONS APPLIED SUCCESSFULLY")
        print("=" * 100)


def export_to_csv(standardizations, filename):
    """Export standardizations to CSV for review/editing"""
    filepath = f"l:/limo/reports/{filename}"
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['original_name', 'canonical_name', 'transaction_count', 'approved'])
        writer.writeheader()
        for std in standardizations:
            std['approved'] = 'YES'  # Default to approved
            writer.writerow(std)
    
    print(f"\n✓ Exported {len(standardizations)} standardizations to:")
    print(f"  {filepath}")
    print(f"\nYou can edit this file and then run:")
    print(f"  python vendor_standardization_tool.py apply {filename}")


def import_from_csv(filename):
    """Import approved standardizations from CSV"""
    filepath = f"l:/limo/reports/{filename}"
    
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return []
    
    standardizations = []
    with open(filepath, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('approved', '').upper() == 'YES':
                standardizations.append(row)
    
    print(f"✓ Loaded {len(standardizations)} approved standardizations from {filename}")
    return standardizations


def generate_report(conn):
    """Generate vendor standardization status report"""
    print("\n" + "=" * 100)
    print("VENDOR STANDARDIZATION STATUS REPORT")
    print("=" * 100)
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Overall stats
    cur.execute("""
        SELECT 
            COUNT(*) as total_receipts,
            COUNT(DISTINCT vendor_name) as unique_vendor_names,
            COUNT(DISTINCT canonical_vendor) as unique_canonical,
            COUNT(CASE WHEN canonical_vendor IS NULL THEN 1 END) as without_canonical
        FROM receipts
        WHERE vendor_name IS NOT NULL
    """)
    stats = cur.fetchone()
    
    print(f"\nOVERALL STATISTICS:")
    print(f"  Total receipts with vendor: {stats['total_receipts']:,}")
    print(f"  Unique vendor names: {stats['unique_vendor_names']:,}")
    print(f"  Unique canonical names: {stats['unique_canonical']:,}")
    print(f"  Without canonical: {stats['without_canonical']:,} ({stats['without_canonical']/stats['total_receipts']*100:.1f}%)")
    
    # Top vendors without standardization
    print(f"\nTOP 20 VENDORS WITHOUT CANONICAL NAME:")
    cur.execute("""
        SELECT vendor_name, COUNT(*) as count
        FROM receipts
        WHERE vendor_name IS NOT NULL 
          AND canonical_vendor IS NULL
        GROUP BY vendor_name
        ORDER BY count DESC
        LIMIT 20
    """)
    
    for row in cur.fetchall():
        print(f"  • {row['vendor_name']:<60} ({row['count']:>5,} receipts)")
    
    # Most common canonical vendors
    print(f"\nTOP 20 CANONICAL VENDORS:")
    cur.execute("""
        SELECT 
            canonical_vendor,
            COUNT(DISTINCT vendor_name) as variations,
            COUNT(*) as receipts
        FROM receipts
        WHERE canonical_vendor IS NOT NULL
        GROUP BY canonical_vendor
        ORDER BY receipts DESC
        LIMIT 20
    """)
    
    for row in cur.fetchall():
        print(f"  • {row['canonical_vendor']:<50} ({row['variations']:>3} variations, {row['receipts']:>6,} receipts)")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    command = sys.argv[1].lower()
    
    conn = psycopg2.connect(**DB_CONFIG)
    
    try:
        if command == 'scan':
            all_vendors = scan_vendor_names(conn)
            print(f"\n✓ Scan complete. Found {len(all_vendors)} unique vendor names.")
            
        elif command == 'analyze':
            all_vendors = scan_vendor_names(conn)
            duplicate_groups = find_duplicates(all_vendors, threshold=0.85)
            print(f"\n✓ Analysis complete. Found {len(duplicate_groups)} duplicate groups.")
            
        elif command == 'standardize':
            all_vendors = scan_vendor_names(conn)
            duplicate_groups = find_duplicates(all_vendors, threshold=0.85)
            
            if not duplicate_groups:
                print("\n✓ No duplicates found!")
                return
            
            standardizations = interactive_standardization(conn, all_vendors, duplicate_groups)
            
            if standardizations:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"vendor_standardizations_{timestamp}.csv"
                export_to_csv(standardizations, filename)
                
                print("\n" + "=" * 100)
                choice = input("Apply these standardizations now? (yes/no): ")
                if choice.lower() in ['yes', 'y']:
                    apply_standardizations(conn, standardizations, dry_run=False)
                else:
                    print("✓ Not applied. Edit the CSV and run 'apply' command when ready.")
            
        elif command == 'apply':
            if len(sys.argv) < 3:
                print("Usage: python vendor_standardization_tool.py apply FILENAME.csv")
                return
            
            filename = sys.argv[2]
            standardizations = import_from_csv(filename)
            
            if standardizations:
                apply_standardizations(conn, standardizations, dry_run=False)
        
        elif command == 'report':
            generate_report(conn)
        
        else:
            print(f"Unknown command: {command}")
            print(__doc__)
    
    finally:
        conn.close()


if __name__ == '__main__':
    main()
