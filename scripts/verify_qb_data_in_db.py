#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Verify which QB export data is actually present in almsdata database.

Analyzes:
- QB Journal/GL exports vs qb_transactions_staging and unified_general_ledger
- Date ranges and transaction counts
- Missing data gaps by year/month
- File-by-file verification status
"""

import os
import sys
import csv
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import psycopg2
import pandas as pd
import argparse
import shutil

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def get_database_coverage(conn):
    """Get what data is already in the database."""
    cur = conn.cursor()
    
    coverage = {}
    
    # QB transactions staging (CRA audit data)
    cur.execute("""
        SELECT 
            COUNT(*) as total_records
        FROM qb_transactions_staging
    """)
    qb_staging = cur.fetchone()
    coverage['qb_staging'] = {
        'records': qb_staging[0],
        'files': 'CRA audit exports (2011-2025)'
    }
    
    # Unified General Ledger
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            MIN(transaction_date) as min_date,
            MAX(transaction_date) as max_date,
            COUNT(DISTINCT source_system) as source_count
        FROM unified_general_ledger
    """)
    ugl = cur.fetchone()
    coverage['ugl'] = {
        'records': ugl[0],
        'date_range': f"{ugl[1]} to {ugl[2]}" if ugl[1] else 'None',
        'sources': ugl[3]
    }
    
    # Journal table
    cur.execute("""
        SELECT 
            COUNT(*) as total
        FROM journal
    """)
    journal = cur.fetchone()
    coverage['journal'] = {
        'records': journal[0],
        'date_range': 'Various dates'
    }
    
    cur.close()
    return coverage

def analyze_excel_export(filepath):
    """
    Analyze Excel QB export to extract transaction counts and date ranges.
    
    Returns: dict with metadata
    """
    try:
        # Try to read Excel file
        df = pd.read_excel(filepath, nrows=1000)  # Sample first 1000 rows for performance
        
        # Look for date columns
        date_columns = [col for col in df.columns if 'date' in col.lower() or 'txn' in col.lower()]
        
        info = {
            'readable': True,
            'rows_sample': len(df),
            'columns': len(df.columns),
            'date_columns': date_columns,
            'has_amounts': any('amount' in col.lower() or 'debit' in col.lower() or 'credit' in col.lower() 
                              for col in df.columns)
        }
        
        # Try to extract date range
        if date_columns:
            for date_col in date_columns:
                try:
                    dates = pd.to_datetime(df[date_col], errors='coerce').dropna()
                    if len(dates) > 0:
                        info['date_range'] = f"{dates.min()} to {dates.max()}"
                        info['transaction_count_estimate'] = len(df)
                        break
                except:
                    pass
        
        return info
        
    except Exception as e:
        return {
            'readable': False,
            'error': str(e)
        }

def analyze_csv_export(filepath):
    """Analyze CSV QB export."""
    try:
        # Read CSV with flexible encoding
        df = pd.read_csv(filepath, nrows=1000, encoding='utf-8', on_bad_lines='skip')
        
        date_columns = [col for col in df.columns if 'date' in col.lower() or 'txn' in col.lower()]
        
        info = {
            'readable': True,
            'rows_sample': len(df),
            'columns': len(df.columns),
            'date_columns': date_columns,
            'has_amounts': any('amount' in col.lower() or 'debit' in col.lower() or 'credit' in col.lower() 
                              for col in df.columns)
        }
        
        if date_columns:
            for date_col in date_columns:
                try:
                    dates = pd.to_datetime(df[date_col], errors='coerce').dropna()
                    if len(dates) > 0:
                        info['date_range'] = f"{dates.min()} to {dates.max()}"
                        info['transaction_count_estimate'] = len(df)
                        break
                except:
                    pass
        
        return info
        
    except Exception as e:
        return {
            'readable': False,
            'error': str(e)
        }

def verify_file_data(file_info, db_coverage):
    """
    Verify if this file's data is present in database.
    
    Returns: (status, recommendation, details)
    """
    filepath = Path(file_info['path'])
    file_type = file_info['type']
    
    # Skip non-export files
    if file_type in ['backup', 'portable']:
        return ('backup_file', 'move_to_backups', 'Backup/portable file - cannot verify without extracting')
    
    if file_type == 'iif_export':
        return ('list_only', 'move_to_iif', 'IIF list export (accounts, items) - no transactions')
    
    # Analyze export files
    if filepath.suffix.lower() == '.xlsx':
        analysis = analyze_excel_export(filepath)
    elif filepath.suffix.lower() == '.csv':
        analysis = analyze_csv_export(filepath)
    else:
        return ('unknown_format', 'review_manual', 'Cannot analyze this file format')
    
    if not analysis.get('readable'):
        return ('unreadable', 'review_manual', f"Cannot read file: {analysis.get('error', 'Unknown error')}")
    
    # Check if it looks like transaction data
    if not analysis.get('has_amounts'):
        return ('no_amounts', 'move_to_verified', 'No amount columns - likely reference data (customers, vendors, etc.)')
    
    # Compare to database coverage
    date_range = analysis.get('date_range', '')
    
    # If we have QB staging data from 2011-2025, exports in that range are likely covered
    if db_coverage['qb_staging']['records'] > 900000:  # We have 983k records
        if date_range and any(str(y) in date_range for y in range(2011, 2026)):
            return ('likely_imported', 'move_to_verified', 
                   f"Date range {date_range} overlaps QB staging (2011-2025, {db_coverage['qb_staging']['records']:,} records)")
    
    # If date range is 2006-2010 or earlier, this is GAP data we need
    if date_range and any(str(y) in date_range for y in range(2003, 2011)):
        return ('gap_data', 'needs_import', 
               f"Date range {date_range} in missing years (2003-2010) - PRIORITY IMPORT")
    
    # Otherwise, uncertain
    return ('uncertain', 'review_manual', 
           f"Date range: {date_range}, Rows: {analysis.get('rows_sample', 'unknown')}")

def organize_qb_files(catalog_csv, conn, dry_run=True):
    """
    Read catalog, verify each file, and organize into qb_storage folders.
    
    Returns: summary dict
    """
    # Read catalog
    with open(catalog_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        files = list(reader)
    
    # Get database coverage
    print("\n" + "="*80)
    print("DATABASE COVERAGE CHECK")
    print("="*80)
    db_coverage = get_database_coverage(conn)
    print(f"\nQB Staging: {db_coverage['qb_staging']['records']:,} records (Files: {db_coverage['qb_staging']['files']})")
    print(f"Unified GL: {db_coverage['ugl']['records']:,} records ({db_coverage['ugl']['date_range']})")
    print(f"Journal:    {db_coverage['journal']['records']:,} records ({db_coverage['journal']['date_range']})")
    
    # Group files by duplicate group
    print("\n" + "="*80)
    print("ANALYZING FILES...")
    print("="*80 + "\n")
    
    dup_groups = defaultdict(list)
    unique_files = []
    
    for file_info in files:
        dup_group = file_info.get('duplicate_group', '')
        if dup_group:
            dup_groups[dup_group].append(file_info)
        else:
            unique_files.append(file_info)
    
    # Organize files
    actions = {
        'move_to_backups': [],
        'move_to_portables': [],
        'move_to_iif': [],
        'move_to_verified': [],
        'needs_import': [],
        'move_to_duplicates': [],
        'review_manual': []
    }
    
    # Process unique files first
    for file_info in unique_files:
        status, action, details = verify_file_data(file_info, db_coverage)
        file_info['verification_status'] = status
        file_info['verification_details'] = details
        
        # Route to appropriate folder
        if file_info['type'] == 'backup':
            action = 'move_to_backups'
        elif file_info['type'] == 'portable':
            action = 'move_to_portables'
        elif file_info['type'] == 'iif_export':
            action = 'move_to_iif'
        
        actions[action].append(file_info)
        
        if status == 'gap_data':
            print(f"[GAP DATA] {file_info['name']}: {details}")
    
    # Process duplicates - keep one, mark others for duplicate folder
    for dup_group, group_files in dup_groups.items():
        # Keep the first one, move rest to duplicates
        keeper = group_files[0]
        status, action, details = verify_file_data(keeper, db_coverage)
        keeper['verification_status'] = status
        keeper['verification_details'] = details
        
        if keeper['type'] == 'backup':
            action = 'move_to_backups'
        elif keeper['type'] == 'portable':
            action = 'move_to_portables'
        elif keeper['type'] == 'iif_export':
            action = 'move_to_iif'
        
        actions[action].append(keeper)
        
        # Mark rest as duplicates
        for dup in group_files[1:]:
            dup['verification_status'] = 'duplicate'
            dup['verification_details'] = f"Duplicate of {keeper['name']}"
            actions['move_to_duplicates'].append(dup)
    
    # Execute moves if not dry run
    print("\n" + "="*80)
    print("FILE ORGANIZATION PLAN")
    print("="*80 + "\n")
    
    target_folders = {
        'move_to_backups': 'l:/limo/qb_storage/backups',
        'move_to_portables': 'l:/limo/qb_storage/portables',
        'move_to_iif': 'l:/limo/qb_storage/iif_lists',
        'move_to_verified': 'l:/limo/qb_storage/exports_verified',
        'needs_import': 'l:/limo/qb_storage/exports_needs_import',
        'move_to_duplicates': 'l:/limo/qb_storage/duplicates',
        'review_manual': 'l:/limo/qb_storage/exports_needs_import'  # Default to needs_import for manual review
    }
    
    summary = {}
    for action, file_list in actions.items():
        print(f"{action:25s}: {len(file_list):4d} files")
        summary[action] = len(file_list)
        
        if not dry_run and file_list:
            target_dir = Path(target_folders[action])
            target_dir.mkdir(parents=True, exist_ok=True)
            
            for file_info in file_list:
                src = Path(file_info['path'])
                if not src.exists():
                    continue
                
                # Avoid name collisions
                dst = target_dir / src.name
                counter = 1
                while dst.exists():
                    dst = target_dir / f"{src.stem}_{counter}{src.suffix}"
                    counter += 1
                
                try:
                    shutil.move(str(src), str(dst))
                except Exception as e:
                    print(f"  ERROR moving {src.name}: {e}")
    
    # Write verification report
    report_path = Path('l:/limo/reports/qb_data_verification.csv')
    with open(report_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = list(files[0].keys()) + ['verification_status', 'verification_details']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for action, file_list in actions.items():
            for file_info in file_list:
                writer.writerow(file_info)
    
    print(f"\n✓ Verification report written to: {report_path}")
    
    return summary, actions

def main():
    parser = argparse.ArgumentParser(description='Verify QB data in database and organize files')
    parser.add_argument('--catalog', default='l:/limo/reports/quickbooks_catalog.csv',
                        help='Path to quickbooks_catalog.csv')
    parser.add_argument('--write', action='store_true',
                        help='Actually move files (default is dry-run)')
    
    args = parser.parse_args()
    
    conn = get_db_connection()
    
    try:
        summary, actions = organize_qb_files(args.catalog, conn, dry_run=not args.write)
        
        # Highlight priority imports
        gap_files = actions.get('needs_import', [])
        if gap_files:
            print("\n" + "="*80)
            print(f"PRIORITY: {len(gap_files)} FILES NEED IMPORT (2003-2010 gap data)")
            print("="*80)
            for f in gap_files[:10]:  # Show first 10
                print(f"  - {f['name']}: {f.get('verification_details', '')}")
            if len(gap_files) > 10:
                print(f"  ... and {len(gap_files) - 10} more")
        
        print("\n" + "="*80)
        print("ORGANIZATION COMPLETE" if not args.write else "DRY RUN COMPLETE")
        print("="*80)
        
        if args.write:
            print("\nFiles moved to l:/limo/qb_storage/")
        else:
            print("\nRe-run with --write to actually move files")
        
        return 0
        
    finally:
        conn.close()

if __name__ == '__main__':
    sys.exit(main())
