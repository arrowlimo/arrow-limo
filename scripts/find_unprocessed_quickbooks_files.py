#!/usr/bin/env python3
"""
Find unprocessed QuickBooks files (QBB, QBW, journal entries, reconcile files).
"""

import os
import glob
from datetime import datetime

print("=" * 80)
print("QUICKBOOKS FILES - PROCESSED VS UNPROCESSED")
print("=" * 80)

# Search for QuickBooks files
qb_patterns = [
    "L:/limo/**/*.qbb",
    "L:/limo/**/*.qbw",
    "L:/limo/**/*.qbm",
    "L:/limo/**/*.qbx",
    "L:/limo/**/*journal*.csv",
    "L:/limo/**/*journal*.xlsx",
    "L:/limo/**/*journal*.xls",
    "L:/limo/**/*reconcile*.csv",
    "L:/limo/**/*reconcile*.xlsx",
    "L:/limo/**/*reconcile*.xls",
]

all_qb_files = []
for pattern in qb_patterns:
    files = glob.glob(pattern, recursive=True)
    all_qb_files.extend(files)

# Remove duplicates
all_qb_files = list(set(all_qb_files))

print(f"\n1. QUICKBOOKS FILES FOUND:")
print("-" * 80)

if all_qb_files:
    # Group by type
    qbb_files = [f for f in all_qb_files if f.lower().endswith('.qbb')]
    qbw_files = [f for f in all_qb_files if f.lower().endswith('.qbw')]
    journal_files = [f for f in all_qb_files if 'journal' in f.lower()]
    reconcile_files = [f for f in all_qb_files if 'reconcile' in f.lower()]
    
    print(f"\nQBB (Backup) files: {len(qbb_files)}")
    for f in sorted(qbb_files):
        size = os.path.getsize(f) / (1024*1024)  # MB
        mod_time = datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d")
        print(f"  {f}")
        print(f"    Size: {size:.1f} MB | Modified: {mod_time}")
    
    print(f"\nQBW (Working) files: {len(qbw_files)}")
    for f in sorted(qbw_files):
        size = os.path.getsize(f) / (1024*1024)  # MB
        mod_time = datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d")
        print(f"  {f}")
        print(f"    Size: {size:.1f} MB | Modified: {mod_time}")
    
    print(f"\nJournal Entry files: {len(journal_files)}")
    for f in sorted(journal_files):
        size = os.path.getsize(f) / 1024  # KB
        mod_time = datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d")
        print(f"  {f}")
        print(f"    Size: {size:.1f} KB | Modified: {mod_time}")
    
    print(f"\nReconcile files: {len(reconcile_files)}")
    for f in sorted(reconcile_files):
        size = os.path.getsize(f) / 1024  # KB
        mod_time = datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d")
        print(f"  {f}")
        print(f"    Size: {size:.1f} KB | Modified: {mod_time}")
else:
    print("  None found")

# Check what's been imported
print("\n\n2. WHAT'S BEEN IMPORTED TO DATABASE:")
print("-" * 80)

import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Check for QuickBooks data markers
cur.execute("""
    SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date)
    FROM banking_transactions
    WHERE description LIKE '%Cheque Expense%'
       OR description LIKE '%Journal%'
""")
qb_count, qb_min, qb_max = cur.fetchone()
print(f"\nQuickBooks-style entries in database: {qb_count:,}")
if qb_min and qb_max:
    print(f"  Date range: {qb_min} to {qb_max}")

# Check for journal entries table
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
      AND table_name ILIKE '%journal%'
""")
journal_tables = cur.fetchall()
if journal_tables:
    print(f"\nJournal tables found:")
    for (table_name,) in journal_tables:
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cur.fetchone()[0]
        print(f"  {table_name}: {count:,} rows")
else:
    print(f"\nNo journal tables found")

cur.close()
conn.close()

print("\n\n3. POTENTIAL UNPROCESSED DATA:")
print("-" * 80)
print("\nQBB/QBW files need to be opened in QuickBooks and exported as:")
print("  - Journal Entry reports (CSV/Excel)")
print("  - General Ledger reports")
print("  - Transaction Detail reports")
print("\nThese exported files can then be imported to the database.")

if journal_files or reconcile_files:
    print(f"\n⚠️  Found {len(journal_files)} journal files and {len(reconcile_files)} reconcile files")
    print("   Check if these have been imported!")
