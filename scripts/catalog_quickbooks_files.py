#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Catalog all QuickBooks files, detect duplicates vs versions, and verify import status.

Handles:
- QBB backups (multiple copies from access attempts)
- QBM portable files
- IIF exports
- XLSX/CSV exports (Journal, GL, Trial Balance, etc.)
- Hash-based duplicate detection
- Import status verification against staging/UGL tables
"""

import os
import sys
import hashlib
import csv
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import psycopg2
import argparse

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def compute_file_hash(filepath):
    """SHA-256 hash of file contents."""
    sha256 = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        return f"ERROR: {e}"

def get_file_info(filepath):
    """Extract file metadata."""
    stat = filepath.stat()
    return {
        'path': str(filepath),
        'name': filepath.name,
        'size': stat.st_size,
        'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
        'extension': filepath.suffix.lower()
    }

def classify_qb_file(filename):
    """Classify QuickBooks file type from filename."""
    fname_lower = filename.lower()
    
    # Backup/portable files
    if '.qbb' in fname_lower:
        return 'backup'
    if '.qbm' in fname_lower:
        return 'portable'
    if '.iif' in fname_lower:
        return 'iif_export'
    
    # Excel/CSV exports
    if 'journal' in fname_lower:
        return 'journal_export'
    if 'general_ledger' in fname_lower or 'general ledger' in fname_lower:
        return 'gl_export'
    if 'trial_balance' in fname_lower or 'trial balance' in fname_lower:
        return 'trial_balance_export'
    if 'profit_and_loss' in fname_lower or 'profit and loss' in fname_lower:
        return 'pl_export'
    if 'balance_sheet' in fname_lower or 'balance sheet' in fname_lower:
        return 'bs_export'
    if 'customer' in fname_lower:
        return 'customer_export'
    if 'supplier' in fname_lower or 'vendor' in fname_lower:
        return 'vendor_export'
    if 'employee' in fname_lower:
        return 'employee_export'
    
    return 'other_export'

def check_import_status(file_info, conn):
    """
    Check if this file's data has been imported into staging/UGL.
    
    Returns: (status, details)
    - 'imported': Data found in staging tables
    - 'not_imported': No matching data found
    - 'partial': Some data found but incomplete
    - 'unknown': Cannot determine
    """
    
    # For now, check if file is in already_imported folders
    if 'already_imported' in file_info['path']:
        return ('archived', 'In already_imported folder')
    
    file_type = classify_qb_file(file_info['name'])
    cur = conn.cursor()
    
    try:
        # Check qb_transactions_staging for imported QB data
        if file_type in ['journal_export', 'gl_export']:
            # Try to match by approximate date range from filename
            # This is heuristic - we'd need to parse the file to be certain
            cur.execute("SELECT COUNT(*) FROM qb_transactions_staging")
            count = cur.fetchone()[0]
            if count > 0:
                return ('possibly_imported', f'QB staging has {count:,} records')
        
        # Check if CRA audit transactions cover the same period
        if file_type == 'backup':
            # Extract year from filename if present
            import re
            year_match = re.search(r'20(\d{2})', file_info['name'])
            if year_match:
                year = f"20{year_match.group(1)}"
                # qb_transactions_staging doesn't have structured date yet - just check for any data
                cur.execute("SELECT COUNT(*) FROM qb_transactions_staging")
                total_count = cur.fetchone()[0]
                if total_count > 0:
                    return ('possibly_imported', f'QB staging has {total_count:,} records (2011-2025)')
        
        return ('unknown', 'Cannot determine without parsing file')
        
    finally:
        cur.close()

def scan_quickbooks_files(root_dir, conn):
    """
    Recursively scan for QuickBooks files and catalog them.
    
    Returns: list of file records
    """
    qb_extensions = {'.qbb', '.qbm', '.iif', '.xlsx', '.csv'}
    qb_keywords = ['quickbooks', 'arrow limousine', 'journal', 'general_ledger', 
                   'trial_balance', 'profit', 'balance_sheet', 'portable']
    
    root_path = Path(root_dir)
    files_found = []
    
    print(f"\n{'='*80}")
    print(f"Scanning {root_dir} for QuickBooks files...")
    print(f"{'='*80}\n")
    
    for ext in qb_extensions:
        for filepath in root_path.rglob(f'*{ext}'):
            # Check if filename suggests QB content
            name_lower = filepath.name.lower()
            is_qb_file = (
                ext in {'.qbb', '.qbm', '.iif'} or
                any(kw in name_lower for kw in qb_keywords) or
                any(kw in str(filepath.parent).lower() for kw in ['quickbooks', 'qbb'])
            )
            
            if not is_qb_file:
                continue
            
            print(f"Processing: {filepath.name}")
            
            # Get file info
            file_info = get_file_info(filepath)
            
            # Compute hash
            file_hash = compute_file_hash(filepath)
            file_info['hash'] = file_hash
            
            # Classify
            file_info['type'] = classify_qb_file(filepath.name)
            
            # Check import status
            status, details = check_import_status(file_info, conn)
            file_info['import_status'] = status
            file_info['import_details'] = details
            
            files_found.append(file_info)
    
    return files_found

def analyze_duplicates(files):
    """
    Group files by hash to identify true duplicates vs different versions.
    
    Returns: (duplicate_groups, unique_files, version_groups)
    """
    # Group by hash
    hash_groups = defaultdict(list)
    for file_info in files:
        if not file_info['hash'].startswith('ERROR'):
            hash_groups[file_info['hash']].append(file_info)
    
    # Classify groups
    duplicate_groups = []  # Same hash, multiple copies
    unique_files = []      # Single file with unique hash
    
    for file_hash, group in hash_groups.items():
        if len(group) > 1:
            duplicate_groups.append({
                'hash': file_hash,
                'count': len(group),
                'files': group,
                'total_size': sum(f['size'] for f in group),
                'size_per_file': group[0]['size']
            })
        else:
            unique_files.append(group[0])
    
    # Group by name to find different versions (same name, different hash)
    name_groups = defaultdict(list)
    for file_info in files:
        if not file_info['hash'].startswith('ERROR'):
            name_groups[file_info['name']].append(file_info)
    
    version_groups = []
    for name, group in name_groups.items():
        # Get unique hashes for this name
        unique_hashes = set(f['hash'] for f in group)
        if len(unique_hashes) > 1:
            version_groups.append({
                'name': name,
                'version_count': len(unique_hashes),
                'total_copies': len(group),
                'versions': []
            })
            
            # Group by hash within this name
            for file_hash in unique_hashes:
                version_files = [f for f in group if f['hash'] == file_hash]
                version_groups[-1]['versions'].append({
                    'hash': file_hash[:16],
                    'files': version_files,
                    'size': version_files[0]['size'],
                    'modified': version_files[0]['modified']
                })
    
    return duplicate_groups, unique_files, version_groups

def generate_report(files, duplicate_groups, unique_files, version_groups, output_path):
    """Generate comprehensive catalog report."""
    
    print(f"\n{'='*80}")
    print(f"QUICKBOOKS FILE CATALOG SUMMARY")
    print(f"{'='*80}\n")
    
    # Overall stats
    total_files = len(files)
    total_size = sum(f['size'] for f in files)
    total_duplicates = sum(g['count'] - 1 for g in duplicate_groups)
    wasted_space = sum(g['total_size'] - g['size_per_file'] for g in duplicate_groups)
    
    print(f"Total QuickBooks files found: {total_files:,}")
    print(f"Total disk space used: {total_size:,} bytes ({total_size/1024/1024:.1f} MB)")
    print(f"True duplicates (same hash): {total_duplicates:,} files")
    print(f"Wasted space from duplicates: {wasted_space:,} bytes ({wasted_space/1024/1024:.1f} MB)")
    print(f"Files with multiple versions (same name, different content): {len(version_groups)}")
    print()
    
    # By type
    print("Files by type:")
    type_counts = defaultdict(int)
    for f in files:
        type_counts[f['type']] += 1
    for ftype, count in sorted(type_counts.items()):
        print(f"  {ftype:25s}: {count:4d} files")
    print()
    
    # By import status
    print("Import status:")
    status_counts = defaultdict(int)
    for f in files:
        status_counts[f['import_status']] += 1
    for status, count in sorted(status_counts.items()):
        print(f"  {status:20s}: {count:4d} files")
    print()
    
    # Write detailed CSV
    csv_path = Path(output_path).with_suffix('.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'name', 'path', 'size', 'modified', 'extension', 'hash', 'type', 
            'import_status', 'import_details', 'duplicate_group'
        ])
        writer.writeheader()
        
        # Add duplicate group ID
        hash_to_group = {}
        for i, group in enumerate(duplicate_groups, 1):
            hash_to_group[group['hash']] = f"DUP-{i:03d}"
        
        for file_info in sorted(files, key=lambda x: (x['type'], x['name'])):
            row = file_info.copy()
            row['duplicate_group'] = hash_to_group.get(file_info['hash'], '')
            writer.writerow(row)
    
    print(f"✓ Detailed catalog written to: {csv_path}")
    
    # Write duplicate report
    dup_path = Path(output_path).with_name('quickbooks_duplicates.csv')
    with open(dup_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Group', 'Hash', 'Count', 'Size_Each', 'Total_Wasted', 'Paths'])
        
        for i, group in enumerate(sorted(duplicate_groups, key=lambda x: x['total_size'], reverse=True), 1):
            paths = ' | '.join([f['path'] for f in group['files']])
            writer.writerow([
                f"DUP-{i:03d}",
                group['hash'][:16],
                group['count'],
                group['size_per_file'],
                group['total_size'] - group['size_per_file'],
                paths
            ])
    
    print(f"✓ Duplicate report written to: {dup_path}")
    
    # Write version variants report
    ver_path = Path(output_path).with_name('quickbooks_versions.csv')
    with open(ver_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Filename', 'Version_Count', 'Total_Copies', 'Hash_Preview', 'Size', 'Modified', 'Paths'])
        
        for group in sorted(version_groups, key=lambda x: x['version_count'], reverse=True):
            for version in group['versions']:
                paths = ' | '.join([vf['path'] for vf in version['files']])
                writer.writerow([
                    group['name'],
                    group['version_count'],
                    len(version['files']),
                    version['hash'],
                    version['size'],
                    version['modified'],
                    paths
                ])
    
    print(f"✓ Version variants report written to: {ver_path}")
    print()
    
    # Action recommendations
    print(f"{'='*80}")
    print("CLEANUP RECOMMENDATIONS")
    print(f"{'='*80}\n")
    
    if duplicate_groups:
        print(f"1. SAFE TO DELETE: {total_duplicates} duplicate files")
        print(f"   Keep 1 copy of each duplicate group, delete the rest")
        print(f"   Recoverable space: {wasted_space/1024/1024:.1f} MB")
        print()
    
    if version_groups:
        print(f"2. REVIEW VERSIONS: {len(version_groups)} files with multiple versions")
        print(f"   Same filename but different content - may need to verify which version is correct")
        print(f"   Check quickbooks_versions.csv for details")
        print()
    
    not_imported = [f for f in files if f['import_status'] == 'unknown']
    if not_imported:
        print(f"3. VERIFY IMPORTS: {len(not_imported)} files with unknown import status")
        print(f"   These may contain data not yet in the database")
        print()

def main():
    parser = argparse.ArgumentParser(description='Catalog QuickBooks files and detect duplicates')
    parser.add_argument('--directory', '-d', default='l:/limo',
                        help='Root directory to scan (default: l:/limo)')
    parser.add_argument('--output', '-o', default='l:/limo/reports/quickbooks_catalog.csv',
                        help='Output path for catalog (default: reports/quickbooks_catalog.csv)')
    
    args = parser.parse_args()
    
    # Ensure output directory exists
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    
    conn = get_db_connection()
    
    try:
        # Scan all QuickBooks files
        files = scan_quickbooks_files(args.directory, conn)
        
        if not files:
            print("No QuickBooks files found!")
            return 1
        
        # Analyze duplicates and versions
        duplicate_groups, unique_files, version_groups = analyze_duplicates(files)
        
        # Generate reports
        generate_report(files, duplicate_groups, unique_files, version_groups, args.output)
        
        return 0
        
    finally:
        conn.close()

if __name__ == '__main__':
    sys.exit(main())
