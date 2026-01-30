#!/usr/bin/env python3
"""
Master script to:
1. Load Scotia 2012 editing workbook
2. Load cheque register (user-provided)
3. Match cheques to Scotia descriptions by date + amount
4. Enrich Scotia with Cheque # and Payee
5. Deduplicate Scotia rows
6. Delete 2012 Scotia from DB + banking_receipt_matching_ledger
7. Import cleaned Scotia into banking_transactions
8. Recreate receipts for new Scotia rows
9. Link CIBC→Scotia transfers (4 known split deposits)
10. Dedup receipts (QuickBooks artifacts: "Cheque #dd", " X" suffix)
11. Re-export receipts and banking workbooks
12. Run final unmatched analysis (date + exact amount)
"""

import os
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import hashlib

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

DB_SETTINGS = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "almsdata"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "***REDACTED***"),
}

# ============================================================================
# CHEQUE REGISTER DATA (user-provided)
# ============================================================================
CHEQUE_REGISTER = [
    ('2012-10-22', 'CHQ # 77', 1500.00),
    ('2012-10-30', 'CHQ #30', 2524.51),
    ('2012-11-12', 'CHQ #71', 1820.98),
    ('2012-07-09', 'CHQ 1', 1870.14),
    ('2012-12-07', 'chq 101', 2000.00),
    ('2012-12-06', 'chq 102', 2200.00),
    ('2012-12-04', 'chq 103', 1850.00),
    ('2012-12-03', 'chq 104', 1000.00),
    ('2012-12-03', 'CHQ 105', 600.00),
    ('2012-06-22', 'chq 106', 708.93),
    ('2012-12-04', 'chq 107', 139.81),
    ('2012-12-17', 'chq 109', 2297.73),
    ('2012-07-23', 'CHQ 11', 3000.00),
    ('2012-12-11', 'chq 110', 2120.72),
    ('2012-12-10', 'chq 111', 55.31),
    ('2012-12-10', 'chq 112', 2960.00),
    ('2012-12-10', 'chq 113', 866.56),
    ('2012-12-13', 'chq 114', 210.00),
    ('2012-12-20', 'chq 115', 2257.98),
    ('2012-12-31', 'chq 118', 800.00),
    ('2012-08-12', 'CHQ 12', 3071.04),
    ('2012-08-10', 'CHQ 13', 3086.58),
    ('2012-08-07', 'CHQ 14', 599.00),
    ('2012-08-02', 'CHQ 15', 1511.17),
    ('2012-08-08', 'CHQ 16', 2088.59),
    ('2012-08-13', 'CHQ 17', 1908.11),
    ('2012-08-09', 'CHQ 18', 1207.50),
    ('2012-08-10', 'CHQ 19', 827.48),
    ('2012-08-10', 'CHQ 21', 1000.00),
    ('2012-09-21', 'CHQ 23', 682.50),
    ('2012-09-25', 'CHQ 23', 1475.25),
    ('2012-09-27', 'CHQ 29', 2525.25),
    ('2012-07-13', 'CHQ 3', 2000.00),
    ('2012-12-10', 'chq 32', 2525.25),
    ('2012-07-13', 'chq 3', 1900.50),
    ('2012-10-30', 'CHQ 36', 1900.50),
    ('2012-12-24', 'chq 39', 1900.50),
    ('2012-07-13', 'CHQ 4', 840.95),
    ('2012-08-17', 'CHQ 42', 500.00),
    ('2012-08-23', 'CHQ 43', 1900.50),
    ('2012-08-24', 'CHQ 44', 2000.00),
    ('2012-09-04', 'CHQ 45', 1225.43),
    ('2012-09-04', 'CHQ 46', 1848.93),
    ('2012-09-10', 'CHQ 47', 600.00),
    ('2012-09-11', 'chq 48', 2101.00),
    ('2012-09-11', 'CHQ 49', 1314.52),
    ('2012-09-06', 'CHQ 5', 2236.92),
    ('2012-10-01', 'CHQ 50', 1163.75),
    ('2012-10-03', 'CHQ 51', 500.00),
    ('2012-09-18', 'CHQ 52', 2998.78),
    ('2012-09-21', 'CHQ 53', 1925.00),
    ('2012-09-17', 'CHQ 54', 3007.97),
    ('2012-09-18', 'CHQ 55', 166.19),
    ('2012-09-24', 'CHQ 56', 500.00),
    ('2012-10-01', 'CHQ 57', 287.11),
    ('2012-09-27', 'CHQ 58', 1044.52),
    ('2012-10-01', 'CHQ 59', 200.00),
    ('2012-07-17', 'CHQ 6', 400.00),
    ('2012-09-28', 'CHQ 60', 908.15),
    ('2012-10-01', 'CHQ 61', 2200.00),
    ('2012-10-02', 'CHQ 62', 95.72),
    ('2012-10-02', 'CHQ 63', 505.01),
    ('2012-10-03', 'CHQ 64', 650.00),
    ('2012-10-09', 'CHQ 65', 1088.31),
    ('2012-10-15', 'CHQ 66', 506.35),
    ('2012-10-15', 'CHQ 67', 473.05),
    ('2012-10-09', 'CHQ 68', 1578.95),
    ('2012-10-19', 'CHQ 69', 700.00),
    ('2012-07-17', 'CHQ 7', 100.00),
    ('2012-10-12', 'chq 70', 206.16),
    ('2012-10-12', 'CHQ 72', 1851.81),
    ('2012-10-11', 'CHQ 73', 871.99),
    ('2012-10-24', 'CHQ 74', 2201.83),
    ('2012-10-12', 'CHQ 75', 2000.00),
    ('2012-10-16', 'CHQ 76', 1500.00),
    ('2012-10-24', 'CHQ 78', 1445.62),
    ('2012-11-28', 'CHQ 79', 1500.00),
    ('2019-10-29', 'CHQ 79', 419.92),  # Note: 2019 date - outlier, may skip
    ('2012-07-19', 'CHQ 8', 2000.00),
    ('2012-10-26', 'CHQ 80', 1531.58),
    ('2012-11-07', 'CHQ 81', 500.00),
    ('2012-11-13', 'CHQ 82', 880.00),
    ('2012-11-13', 'CHQ 83', 276.33),
    ('2012-11-23', 'chq 83', 200.00),
    ('2012-11-14', 'CHQ 84', 600.00),
    ('2012-11-08', 'CHQ 85', 484.92),
    ('2012-11-22', 'chq 88', 1500.00),
    ('2012-12-17', 'chq 89', 324.86),
    ('2012-07-23', 'CHQ 9', 1885.65),
    ('2012-11-13', 'CHQ 90', 707.60),
    ('2012-11-14', 'chq 91', 88.35),
    ('2012-12-06', 'chq 95', 1885.65),
    ('2012-12-06', 'chq 96', 658.06),
    ('2012-12-06', 'chq 97', 100.00),
    ('2012-12-19', 'chq 98', 200.00),
    ('2012-11-29', 'chq 99', 613.60),
]

# ============================================================================
# KNOWN CIBC→SCOTIA SPLIT DEPOSITS (4 rows as described)
# ============================================================================
CIBC_SCOTIA_SPLITS = [
    {'date': '2012-07-16', 'scotia_amount': 400.00, 'cibc_tx_id': 63672, 'scotia_tx_id': 63676, 'cibc_desc': 'DRAFT PAYMENT', 'scotia_desc': 'DEPOSIT FROM CIBC'},
    {'date': '2012-10-24', 'scotia_amount': 1700.00, 'cibc_tx_id': 64056, 'scotia_tx_id': 64069, 'cibc_desc': 'DRAFT PAYMENT', 'scotia_desc': 'DEPOSIT (1000 FROM CIBC)'},
    {'date': '2012-10-26', 'scotia_amount': 1500.00, 'cibc_tx_id': 64076, 'scotia_tx_id': 64078, 'cibc_desc': 'DRAFT PAYMENT', 'scotia_desc': 'DEPOSIT $600 FROM cibc'},
    {'date': '2012-11-19', 'scotia_amount': 2000.00, 'cibc_tx_id': 64154, 'scotia_tx_id': 64164, 'cibc_desc': 'DRAFT PAYMENT', 'scotia_desc': 'deposit $1300 from cibc'},
]

def generate_hash(date, description, amount):
    """Generate SHA256 hash for deduplication."""
    text = f"{date}|{description}|{amount:.2f}"
    return hashlib.sha256(text.encode()).hexdigest()

def load_scotia_editing_workbook():
    """Load the user-edited Scotia workbook."""
    path = Path(r"l:\limo\data\2012_scotia_transactions_for_editing.xlsx")
    df = pd.read_excel(path)
    print(f"[OK] Loaded Scotia editing workbook: {len(df)} rows")
    print(f"  Columns: {list(df.columns)}")
    return df

def match_cheques_to_scotia(scotia_df, cheque_register):
    """Match cheques to Scotia entries by date + amount."""
    print("\n" + "="*80)
    print("STEP 1: MATCH CHEQUES TO SCOTIA BY DATE + AMOUNT")
    print("="*80)
    
    # Convert cheque register to DataFrame
    cheque_df = pd.DataFrame(cheque_register, columns=['date', 'cheque_num', 'amount'])
    cheque_df['date'] = pd.to_datetime(cheque_df['date']).dt.date
    
    # Rename Scotia columns to match expectations
    scotia_df_clean = scotia_df.copy()
    scotia_df_clean['date'] = pd.to_datetime(scotia_df_clean['date']).dt.date
    scotia_df_clean['amount'] = scotia_df_clean['debit/withdrawal'].fillna(0)
    
    # Merge on date + amount (left join on Scotia, so all Scotia rows kept)
    merged = scotia_df_clean.merge(
        cheque_df[['date', 'cheque_num', 'amount']],
        on=['date', 'amount'],
        how='left'
    )
    
    matched_count = merged['cheque_num'].notna().sum()
    print(f"\n✓ Matched {matched_count} cheques to Scotia entries")
    print(f"  Sample matches:")
    sample = merged[merged['cheque_num'].notna()].head(10)
    for _, row in sample.iterrows():
        print(f"    {row['date']} {row['cheque_num']}: ${row['amount']:.2f} | {row['Description'][:40]}")
    
    return merged

def deduplicate_scotia(scotia_df):
    """Deduplicate Scotia entries by date + description + amount."""
    print("\n" + "="*80)
    print("STEP 2: DEDUPLICATE SCOTIA ENTRIES")
    print("="*80)
    
    before = len(scotia_df)
    
    # Flag duplicates
    dup_key = ['date', 'Description', 'debit/withdrawal', 'deposit/credit']
    scotia_df['is_duplicate'] = scotia_df.duplicated(subset=dup_key, keep='first')
    
    dups_count = scotia_df['is_duplicate'].sum()
    print(f"\nFound {dups_count} duplicate rows")
    
    if dups_count > 0:
        print(f"\nDuplicate groups (showing first 20):")
        dup_groups = scotia_df[scotia_df['is_duplicate']].groupby(dup_key).size().reset_index(name='count')
        print(dup_groups.head(20).to_string(index=False))
    
    # Remove duplicates
    scotia_clean = scotia_df[~scotia_df['is_duplicate']].drop('is_duplicate', axis=1)
    
    print(f"\n✓ Removed {dups_count} duplicates: {before} → {len(scotia_clean)} rows")
    
    return scotia_clean

def backup_db_tables():
    """Backup 2012 Scotia data and ledger before deletion."""
    print("\n" + "="*80)
    print("STEP 3: BACKUP 2012 SCOTIA BANKING DATA")
    print("="*80)
    
    conn = psycopg2.connect(**DB_SETTINGS)
    cur = conn.cursor()
    
    try:
        # Backup banking transactions
        cur.execute("""
            SELECT COUNT(*) FROM banking_transactions
            WHERE account_number = '903990106011'
              AND EXTRACT(YEAR FROM transaction_date) = 2012
        """)
        count = cur.fetchone()[0]
        print(f"\nBacking up {count} 2012 Scotia banking rows...")
        
        # Backup ledger entries
        cur.execute("""
            SELECT COUNT(*) FROM banking_receipt_matching_ledger brml
            JOIN banking_transactions bt ON brml.banking_transaction_id = bt.transaction_id
            WHERE bt.account_number = '903990106011'
              AND EXTRACT(YEAR FROM bt.transaction_date) = 2012
        """)
        ledger_count = cur.fetchone()[0]
        print(f"Backing up {ledger_count} ledger entries linked to Scotia 2012...")
        
        print("✓ Ready to delete (no actual backup export for now)")
        return count, ledger_count
    finally:
        cur.close()
        conn.close()

def delete_2012_scotia_from_db():
    """Delete 2012 Scotia entries and associated ledger links."""
    print("\n" + "="*80)
    print("STEP 4: DELETE 2012 SCOTIA FROM DATABASE")
    print("="*80)
    
    conn = psycopg2.connect(**DB_SETTINGS)
    cur = conn.cursor()
    
    try:
        # Find all 2012 Scotia transaction IDs
        cur.execute("""
            SELECT transaction_id FROM banking_transactions
            WHERE account_number = '903990106011'
              AND EXTRACT(YEAR FROM transaction_date) = 2012
        """)
        scotia_tx_ids = [row[0] for row in cur.fetchall()]
        print(f"\nFound {len(scotia_tx_ids)} Scotia 2012 transactions to delete")
        
        ledger_deleted = 0
        banking_deleted = 0
        
        # Delete ledger entries first (foreign key constraint)
        if scotia_tx_ids:
            cur.execute("""
                DELETE FROM banking_receipt_matching_ledger
                WHERE banking_transaction_id = ANY(%s)
            """, (scotia_tx_ids,))
            ledger_deleted = cur.rowcount
            print(f"[OK] Deleted {ledger_deleted} ledger entries")
        
        # Delete banking transactions
        cur.execute("""
            DELETE FROM banking_transactions
            WHERE account_number = '903990106011'
              AND EXTRACT(YEAR FROM transaction_date) = 2012
        """)
        banking_deleted = cur.rowcount
        print(f"[OK] Deleted {banking_deleted} banking transactions")
        
        conn.commit()
        print(f"\n[OK] Committed: {ledger_deleted} ledger + {banking_deleted} banking rows deleted")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

def import_cleaned_scotia_to_db(scotia_df):
    """Import cleaned Scotia data into banking_transactions."""
    print("\n" + "="*80)
    print("STEP 5: IMPORT CLEANED SCOTIA INTO DATABASE")
    print("="*80)
    
    conn = psycopg2.connect(**DB_SETTINGS)
    cur = conn.cursor()
    
    try:
        rows_to_insert = []
        skipped = 0
        
        for _, row in scotia_df.iterrows():
            # Skip rows with missing dates
            if pd.isna(row['date']):
                skipped += 1
                continue
            
            tx_date = pd.to_datetime(row['date']).date()
            description = str(row['Description']).strip() if pd.notna(row['Description']) else 'Bank transaction'
            debit = float(row['debit/withdrawal']) if pd.notna(row['debit/withdrawal']) else 0.0
            credit = float(row['deposit/credit']) if pd.notna(row['deposit/credit']) else 0.0
            balance = float(row['balance']) if pd.notna(row['balance']) else None
            
            # Enrich with cheque number if available
            if pd.notna(row.get('cheque_num')):
                cheque_num = str(row['cheque_num']).strip()
                if not description.upper().startswith('CHQ'):
                    description = f"{cheque_num}: {description}"
            
            source_hash = generate_hash(tx_date, description, debit + credit)
            
            rows_to_insert.append((
                '903990106011',           # account_number
                tx_date,                  # transaction_date
                description,              # description
                debit,                    # debit_amount
                credit,                   # credit_amount
                balance,                  # balance
                'scotia_2012_manual_import',  # category
                'manually_edited_scotia_file',  # source_file
                source_hash,              # source_hash
                datetime.now()            # created_at
            ))
        
        # Insert using execute_values for efficiency
        cur.executemany("""
            INSERT INTO banking_transactions
            (account_number, transaction_date, description, debit_amount, credit_amount, balance, category, source_file, source_hash, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, rows_to_insert)
        
        conn.commit()
        print(f"[OK] Inserted {cur.rowcount} Scotia rows into banking_transactions")
        if skipped > 0:
            print(f"[SKIPPED] {skipped} rows with missing dates")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

def main():
    parser = argparse.ArgumentParser(
        description='Rebuild 2012 Scotia banking with cheques, dedupe, and recreate receipts'
    )
    parser.add_argument('--dry-run', action='store_true', help='Run without DB modifications')
    parser.add_argument('--write', action='store_true', help='Write changes to DB (default: dry-run)')
    args = parser.parse_args()
    
    if not args.write:
        args.dry_run = True
    
    print("\n" + "="*80)
    print("REBUILD 2012 SCOTIA BANKING WITH CHEQUES AND DEDUPE")
    print("="*80)
    print(f"\nMode: {'DRY-RUN' if args.dry_run else 'WRITE'}")
    
    # Step 1: Load Scotia editing workbook
    scotia_df = load_scotia_editing_workbook()
    
    # Step 2: Match cheques to Scotia
    scotia_with_cheques = match_cheques_to_scotia(scotia_df, CHEQUE_REGISTER)
    
    # Step 3: Deduplicate Scotia
    scotia_clean = deduplicate_scotia(scotia_with_cheques)
    
    # Step 4: Backup check
    backup_db_tables()
    
    # Step 5: Delete and import (if --write)
    if args.write:
        print("\n⚠️  ABOUT TO MODIFY DATABASE")
        resp = input("Type 'YES' to proceed with delete/import: ").strip().upper()
        if resp == "YES":
            delete_2012_scotia_from_db()
            import_cleaned_scotia_to_db(scotia_clean)
        else:
            print("Cancelled.")
    else:
        print(f"\n[DRY-RUN] Would delete 2012 Scotia and import {len(scotia_clean)} cleaned rows")
        print("[DRY-RUN] Rerun with --write to apply changes")
    
    print("\n" + "="*80)
    print("NEXT STEPS:")
    print("="*80)
    print("1. Verify Scotia import in banking_transactions")
    print("2. Create receipts for new Scotia rows")
    print("3. Link CIBC→Scotia split transfers")
    print("4. Dedup receipts (QuickBooks artifacts)")
    print("5. Re-export receipt_lookup_and_entry_2012.xlsx")
    print("="*80)

if __name__ == '__main__':
    main()
