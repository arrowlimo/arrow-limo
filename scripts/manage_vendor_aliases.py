#!/usr/bin/env python3
"""
Vendor Manual Alias Management System
=====================================

This tool helps build and maintain a manually-verified vendor alias mapping,
starting with 2019 receipts where business owners verified actual vendor names.

Example: "LD 67 street red deer" was manually verified to be "Liquor Depot"
"""

import psycopg2
import csv
import re
from collections import defaultdict
from difflib import SequenceMatcher

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def load_manual_aliases():
    """Load manually verified vendor aliases from CSV."""
    aliases = {}
    
    try:
        with open('l:/limo/data/vendor_manual_aliases.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                historical = row['historical_name'].strip().upper()
                canonical = row['canonical_name'].strip()
                confidence = float(row['confidence'])
                
                aliases[historical] = {
                    'canonical': canonical,
                    'confidence': confidence,
                    'year': row['year_identified'],
                    'notes': row['notes']
                }
    except FileNotFoundError:
        print("⚠️  Manual aliases file not found. Starting with empty mapping.")
        return {}
    
    return aliases

def find_similar_vendors(target_vendor, all_vendors, threshold=0.8):
    """Find vendors similar to the target using fuzzy matching."""
    similar = []
    target_upper = target_vendor.upper()
    
    for vendor in all_vendors:
        vendor_upper = vendor.upper()
        
        # Exact match
        if target_upper == vendor_upper:
            similar.append((vendor, 1.0, 'exact'))
            continue
        
        # Substring match
        if target_upper in vendor_upper or vendor_upper in target_upper:
            similar.append((vendor, 0.95, 'substring'))
            continue
        
        # Fuzzy match
        ratio = SequenceMatcher(None, target_upper, vendor_upper).ratio()
        if ratio >= threshold:
            similar.append((vendor, ratio, 'fuzzy'))
    
    # Sort by confidence descending
    similar.sort(key=lambda x: x[1], reverse=True)
    return similar

def analyze_2019_vendors():
    """Analyze 2019 vendors to help identify manual mappings."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get all unique vendors from 2019
    cur.execute("""
        SELECT vendor_name, COUNT(*) as receipt_count, SUM(gross_amount) as total_amount
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2019
        AND vendor_name IS NOT NULL
        GROUP BY vendor_name
        ORDER BY receipt_count DESC
    """)
    
    vendors_2019 = []
    for vendor, count, amount in cur.fetchall():
        vendors_2019.append({
            'name': vendor,
            'count': count,
            'amount': float(amount or 0)
        })
    
    cur.close()
    conn.close()
    
    return vendors_2019

def find_vendor_groups(vendors_2019, manual_aliases):
    """Group 2019 vendors that should be consolidated based on manual aliases."""
    
    groups = defaultdict(list)
    
    # First, use manual aliases to seed groups
    for vendor_data in vendors_2019:
        vendor_name = vendor_data['name']
        vendor_upper = vendor_name.upper()
        
        # Check if this vendor has a manual alias
        matched = False
        for historical_name, alias_info in manual_aliases.items():
            if historical_name in vendor_upper or vendor_upper in historical_name:
                canonical = alias_info['canonical']
                groups[canonical].append({
                    **vendor_data,
                    'match_type': 'manual_alias',
                    'confidence': alias_info['confidence']
                })
                matched = True
                break
        
        if not matched:
            # No manual alias, keep as separate for now
            groups[vendor_name].append({
                **vendor_data,
                'match_type': 'no_match',
                'confidence': 1.0
            })
    
    return groups

def suggest_new_aliases(vendors_2019, manual_aliases):
    """Suggest new vendor aliases based on pattern analysis."""
    
    suggestions = []
    all_vendor_names = [v['name'] for v in vendors_2019]
    
    # Common patterns to look for
    patterns = [
        (r'(CENTEX|FAS GAS|SHELL|ESSO|CO-OP|PETRO|HUSKY).*', 'Fuel Station'),
        (r'(LIQUOR|LCBO|BEER STORE|WINE|PLENTY).*', 'Liquor & Beverage'),
        (r'(HEFFNER|AUTO FINANCE|FINANCING).*', 'Heffner Auto Finance'),
        (r'(INSURANCE|SGI|AVIVA|JEVCO).*', 'Insurance Services'),
        (r'(RESTAURANT|FOOD|DINING|CAFE).*', 'Restaurant/Food Services'),
        (r'(HOTEL|MOTEL|INN|LODGE).*', 'Accommodation'),
        (r'(STAPLES|OFFICE DEPOT|OFFICE SUPPLY).*', 'Office Supplies'),
        (r'(CANADIAN TIRE|MIDAS|JIFFY|AUTO REPAIR).*', 'Vehicle Maintenance'),
    ]
    
    for vendor_data in vendors_2019:
        vendor_name = vendor_data['name']
        vendor_upper = vendor_name.upper()
        
        # Skip if already has manual alias
        if any(hist in vendor_upper or vendor_upper in hist for hist in manual_aliases.keys()):
            continue
        
        # Check patterns
        for pattern, canonical_suggestion in patterns:
            if re.search(pattern, vendor_upper):
                suggestions.append({
                    'vendor': vendor_name,
                    'count': vendor_data['count'],
                    'amount': vendor_data['amount'],
                    'suggested_canonical': canonical_suggestion,
                    'confidence': 0.8,
                    'reason': f'Pattern match: {pattern}'
                })
                break
    
    # Sort by amount (high-value vendors first)
    suggestions.sort(key=lambda x: x['amount'], reverse=True)
    return suggestions

def export_manual_alias_template(vendors_2019, manual_aliases):
    """Export a template CSV for manual alias entry."""
    
    suggestions = suggest_new_aliases(vendors_2019, manual_aliases)
    
    # Take top 100 by amount for manual review
    top_suggestions = suggestions[:100]
    
    with open('l:/limo/data/vendor_manual_aliases_SUGGESTED.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'historical_name',
            'canonical_name',
            'year_identified',
            'confidence',
            'notes',
            'receipt_count',
            'total_amount',
            'suggested_reason'
        ])
        
        for suggestion in top_suggestions:
            writer.writerow([
                suggestion['vendor'],
                suggestion['suggested_canonical'],
                '2019',
                suggestion['confidence'],
                suggestion['reason'],
                suggestion['count'],
                f"${suggestion['amount']:.2f}",
                'Auto-suggested, needs verification'
            ])
    
    print(f"\n✅ Exported {len(top_suggestions)} suggested aliases to:")
    print(f"   l:/limo/data/vendor_manual_aliases_SUGGESTED.csv")
    print(f"\nReview this file, update canonical names as needed, then add to:")
    print(f"   l:/limo/data/vendor_manual_aliases.csv")

def apply_manual_aliases_to_database(dry_run=True):
    """Apply manual aliases to receipts table (creates canonical_vendor field)."""
    
    manual_aliases = load_manual_aliases()
    
    if not manual_aliases:
        print("❌ No manual aliases loaded. Please populate vendor_manual_aliases.csv first.")
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check if canonical_vendor column exists
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'receipts' AND column_name = 'canonical_vendor'
    """)
    
    if not cur.fetchone():
        print("Creating canonical_vendor column...")
        cur.execute("""
            ALTER TABLE receipts 
            ADD COLUMN IF NOT EXISTS canonical_vendor VARCHAR(255)
        """)
        conn.commit()
    
    # Apply aliases
    total_updated = 0
    
    for historical_name, alias_info in manual_aliases.items():
        canonical = alias_info['canonical']
        confidence = alias_info['confidence']
        
        # Find receipts matching this historical name (fuzzy)
        cur.execute("""
            SELECT receipt_id, vendor_name
            FROM receipts
            WHERE UPPER(vendor_name) LIKE %s
            AND (canonical_vendor IS NULL OR canonical_vendor != %s)
        """, (f'%{historical_name}%', canonical))
        
        matches = cur.fetchall()
        
        if matches:
            print(f"\n{canonical}:")
            print(f"  Historical name: {historical_name}")
            print(f"  Matches found: {len(matches)}")
            print(f"  Confidence: {confidence}")
            
            if not dry_run:
                # Update receipts
                receipt_ids = [m[0] for m in matches]
                cur.execute("""
                    UPDATE receipts
                    SET canonical_vendor = %s
                    WHERE receipt_id = ANY(%s)
                """, (canonical, receipt_ids))
                
                total_updated += len(matches)
                print(f"  ✅ Updated {len(matches)} receipts")
            else:
                # Show sample
                for rid, vname in matches[:3]:
                    print(f"    - {vname}")
                if len(matches) > 3:
                    print(f"    + {len(matches)-3} more...")
    
    if dry_run:
        print("\n" + "="*80)
        print("DRY RUN COMPLETE - No changes made to database")
        print("Run with --write to apply changes")
        conn.rollback()
    else:
        conn.commit()
        print("\n" + "="*80)
        print(f"✅ APPLIED: {total_updated} receipts updated with canonical vendor names")
    
    cur.close()
    conn.close()

def show_vendor_consolidation_impact():
    """Show impact of applying manual aliases."""
    
    manual_aliases = load_manual_aliases()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("VENDOR CONSOLIDATION IMPACT (Manual Aliases)")
    print("="*80)
    
    # Show canonical vendors and their receipt counts
    cur.execute("""
        SELECT 
            canonical_vendor,
            COUNT(DISTINCT vendor_name) as name_variants,
            COUNT(*) as receipt_count,
            SUM(gross_amount) as total_amount
        FROM receipts
        WHERE canonical_vendor IS NOT NULL
        GROUP BY canonical_vendor
        ORDER BY receipt_count DESC
    """)
    
    print("\nCanonical Vendor Summary:")
    print("-" * 80)
    
    total_receipts = 0
    total_amount = 0
    
    for canonical, variants, count, amount in cur.fetchall():
        total_receipts += count
        total_amount += float(amount or 0)
        print(f"{canonical:.<40} {variants:>3} variants, {count:>5} receipts, ${amount:>12,.2f}")
    
    print("-" * 80)
    print(f"{'TOTAL':.<40} {total_receipts:>14} receipts, ${total_amount:>12,.2f}")
    
    # Show receipts without canonical vendor
    cur.execute("""
        SELECT COUNT(*) FROM receipts WHERE canonical_vendor IS NULL
    """)
    without_canonical = cur.fetchone()[0]
    
    cur.execute("""
        SELECT COUNT(*) FROM receipts
    """)
    total = cur.fetchone()[0]
    
    pct_mapped = (total_receipts / total * 100) if total > 0 else 0
    
    print(f"\nReceipts mapped to canonical vendors: {total_receipts:,} of {total:,} ({pct_mapped:.1f}%)")
    print(f"Receipts still needing mapping: {without_canonical:,}")
    
    cur.close()
    conn.close()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Vendor Manual Alias Management')
    parser.add_argument('--analyze-2019', action='store_true', 
                       help='Analyze 2019 vendors and suggest aliases')
    parser.add_argument('--apply', action='store_true',
                       help='Apply manual aliases to database')
    parser.add_argument('--write', action='store_true',
                       help='Actually write changes (default is dry-run)')
    parser.add_argument('--show-impact', action='store_true',
                       help='Show consolidation impact of current aliases')
    parser.add_argument('--export-template', action='store_true',
                       help='Export suggested alias template for manual review')
    
    args = parser.parse_args()
    
    if args.analyze_2019 or args.export_template:
        print("Analyzing 2019 vendors...")
        vendors_2019 = analyze_2019_vendors()
        print(f"Found {len(vendors_2019)} unique vendors in 2019")
        
        manual_aliases = load_manual_aliases()
        print(f"Loaded {len(manual_aliases)} manual aliases")
        
        if args.export_template:
            export_manual_alias_template(vendors_2019, manual_aliases)
    
    if args.apply:
        apply_manual_aliases_to_database(dry_run=not args.write)
    
    if args.show_impact:
        show_vendor_consolidation_impact()
    
    if not any([args.analyze_2019, args.apply, args.show_impact, args.export_template]):
        # Default: show current aliases
        manual_aliases = load_manual_aliases()
        
        print("\n" + "="*80)
        print("CURRENT MANUAL VENDOR ALIASES")
        print("="*80)
        
        if not manual_aliases:
            print("\nNo manual aliases loaded yet.")
            print("\nTo get started:")
            print("  1. python scripts/manage_vendor_aliases.py --analyze-2019 --export-template")
            print("  2. Review l:/limo/data/vendor_manual_aliases_SUGGESTED.csv")
            print("  3. Add verified entries to l:/limo/data/vendor_manual_aliases.csv")
            print("  4. python scripts/manage_vendor_aliases.py --apply --write")
        else:
            print(f"\nTotal aliases: {len(manual_aliases)}")
            print("\nAlias List:")
            print("-" * 80)
            
            for historical, info in sorted(manual_aliases.items()):
                print(f"{historical:.<40} → {info['canonical']}")
                print(f"{'':.<40}   {info['notes']}")
                print()

if __name__ == '__main__':
    main()
