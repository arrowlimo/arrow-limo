#!/usr/bin/env python3
"""
Process split receipts in the Excel file to assign proper receipt IDs.

Split receipts have the pattern "SPLIT/{total_amount}" in the description field.
All lines with the same date, vendor, and split amount should share the same receipt ID.

This script:
1. Analyzes the Excel file for SPLIT patterns
2. Groups split receipts by (date, vendor, split_amount)
3. Assigns unique receipt IDs to each group
4. Validates that split totals match the sum of individual amounts
5. Creates a corrected Excel file with proper receipt IDs

Usage:
  python scripts/fix_split_receipt_ids.py --dry-run    # Preview only
  python scripts/fix_split_receipt_ids.py --fix       # Create corrected file
"""
import os
import sys
import argparse
import pandas as pd
import re
from collections import defaultdict

XLSX_PATH = r"L:\limo\reports\new receipts fileoct.xlsx"
OUTPUT_PATH = r"L:\limo\reports\receipts_with_fixed_ids.xlsx"

def analyze_split_receipts(df):
    """Analyze split receipt patterns in the data"""
    print("🔍 Analyzing split receipt patterns...")
    
    # Find SPLIT patterns in description
    split_pattern = re.compile(r'SPLIT/([0-9.]+)', re.IGNORECASE)
    split_records = []
    
    for idx, row in df.iterrows():
        desc = str(row.get('description', '')).strip()
        match = split_pattern.search(desc)
        
        if match:
            split_total = float(match.group(1))
            split_records.append({
                'row_idx': idx,
                'receipt_date': row['receipt_date'],
                'vendor_name': row['vendor_name'],
                'description': desc,
                'expense': row.get('expense', 0),
                'split_total': split_total,
                'original_id': row.get('id')
            })
    
    print(f"Found {len(split_records)} records with SPLIT patterns")
    
    return split_records

def group_split_receipts(split_records):
    """Group split receipts by date, vendor, and split amount"""
    print("📋 Grouping split receipts...")
    
    groups = defaultdict(list)
    
    for record in split_records:
        # Create a key for grouping: (date, vendor, split_total)
        key = (
            record['receipt_date'],
            record['vendor_name'].strip().upper(),
            record['split_total']
        )
        groups[key].append(record)
    
    print(f"Found {len(groups)} unique split receipt groups")
    
    # Analyze each group
    group_analysis = []
    for key, records in groups.items():
        date, vendor, split_total = key
        
        individual_totals = sum(rec['expense'] for rec in records)
        difference = abs(split_total - individual_totals)
        
        group_info = {
            'date': date,
            'vendor': vendor,
            'split_total': split_total,
            'line_count': len(records),
            'individual_total': individual_totals,
            'difference': difference,
            'records': records,
            'matches': difference < 0.01  # Allow for small rounding differences
        }
        
        group_analysis.append(group_info)
    
    return group_analysis

def preview_split_groups(group_analysis):
    """Show preview of split receipt groups"""
    print("\n📊 Split Receipt Groups Analysis:")
    
    matching_groups = [g for g in group_analysis if g['matches']]
    problem_groups = [g for g in group_analysis if not g['matches']]
    
    print(f"[OK] Matching groups (totals match): {len(matching_groups)}")
    print(f"[WARN]  Problem groups (totals don't match): {len(problem_groups)}")
    
    if matching_groups:
        print(f"\n📝 Sample Matching Groups:")
        for i, group in enumerate(matching_groups[:5]):
            print(f"  {i+1}. {group['date']} - {group['vendor']}")
            print(f"     Split total: ${group['split_total']:.2f}, Lines: {group['line_count']}, Sum: ${group['individual_total']:.2f}")
            for j, rec in enumerate(group['records'][:3]):
                print(f"       Line {j+1}: ${rec['expense']:.2f} - {rec['description'][:50]}...")
    
    if problem_groups:
        print(f"\n[WARN]  Problem Groups (need manual review):")
        for i, group in enumerate(problem_groups):
            print(f"  {i+1}. {group['date']} - {group['vendor']}")
            print(f"     Split total: ${group['split_total']:.2f}, Sum: ${group['individual_total']:.2f}, Diff: ${group['difference']:.2f}")
    
    return matching_groups, problem_groups

def assign_receipt_ids(df, group_analysis):
    """Assign proper receipt IDs to split receipts"""
    print("\n🔧 Assigning receipt IDs to split groups...")
    
    df_copy = df.copy()
    
    # Start with a high ID number to avoid conflicts with existing IDs
    next_receipt_id = 100000
    assignments_made = 0
    
    for group in group_analysis:
        if group['matches']:  # Only process matching groups
            # Assign the same receipt ID to all records in this group
            for record in group['records']:
                row_idx = record['row_idx']
                df_copy.loc[row_idx, 'id'] = next_receipt_id
                assignments_made += 1
            
            next_receipt_id += 1
    
    print(f"[OK] Assigned receipt IDs to {assignments_made} split receipt lines")
    print(f"📊 Created {next_receipt_id - 100000} unique receipt groups")
    
    return df_copy

def main():
    parser = argparse.ArgumentParser(description='Fix split receipt IDs')
    parser.add_argument('--dry-run', action='store_true', help='Preview analysis only')
    parser.add_argument('--fix', action='store_true', help='Create corrected Excel file')
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.fix:
        print("[FAIL] Must specify either --dry-run or --fix")
        sys.exit(1)
    
    if not os.path.exists(XLSX_PATH):
        print(f"[FAIL] Excel file not found: {XLSX_PATH}")
        sys.exit(1)
    
    try:
        # Load Excel file
        print(f"📊 Loading Excel file: {XLSX_PATH}")
        xl = pd.ExcelFile(XLSX_PATH)
        df = xl.parse('receipts')
        print(f"📋 Total records: {len(df)}")
        
        # Analyze split receipts
        split_records = analyze_split_receipts(df)
        
        if not split_records:
            print("ℹ️  No split receipts found")
            return
        
        # Group split receipts
        group_analysis = group_split_receipts(split_records)
        
        # Preview groups
        matching_groups, problem_groups = preview_split_groups(group_analysis)
        
        if args.fix:
            if problem_groups:
                print(f"\n[WARN]  Warning: {len(problem_groups)} groups have mismatched totals")
                response = input("Continue with fix anyway? (y/N): ")
                if response.lower() != 'y':
                    print("[FAIL] Cancelled by user")
                    return
            
            # Assign receipt IDs
            df_corrected = assign_receipt_ids(df, group_analysis)
            
            # Save corrected file
            print(f"\n💾 Saving corrected file: {OUTPUT_PATH}")
            df_corrected.to_excel(OUTPUT_PATH, sheet_name='receipts', index=False)
            
            print(f"[OK] Successfully created corrected receipts file")
            print(f"📁 File saved to: {OUTPUT_PATH}")
            
        elif args.dry_run:
            print(f"\n💡 To create corrected file with proper receipt IDs, run:")
            print(f"   python scripts/fix_split_receipt_ids.py --fix")
            
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()