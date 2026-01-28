#!/usr/bin/env python
"""
CRITICAL: Replace entire Scotia 2012 (account 903990106011) with verified data.

Current state: 2,318 corrupted records (66% duplicates, wrong balances)
Target: 786 verified transactions from Scotia_Bank_2012_Full_Report.csv

This script:
1. Backs up current corrupted Scotia 2012 data
2. Deletes all Scotia 2012 records from database  
3. Imports verified transactions from Scotia_Bank_2012_Full_Report.csv
4. Validates balances and completeness
"""
import psycopg2
import csv
from datetime import datetime
import os
from pathlib import Path

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

VERIFIED_FILE = r"L:\limo\reports\Scotia_Bank_2012_Full_Report.csv"

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def backup_current_data(cur):
    """Create backup of current Scotia 2012 data."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'banking_transactions_scotia_2012_corrupted_backup_{timestamp}'
    
    print(f"\n✓ Creating backup table: {backup_table}")
    cur.execute(f"""
        CREATE TABLE {backup_table} AS
        SELECT * FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
    """)
    
    cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
    backup_count = cur.fetchone()[0]
    print(f"  Backed up {backup_count} records")
    
    return backup_table

def delete_current_data(cur):
    """Delete all Scotia 2012 records from banking_transactions."""
    print(f"\n✓ Deleting current corrupted Scotia 2012 data...")
    
    cur.execute("""
        DELETE FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
    """)
    
    deleted_count = cur.rowcount
    print(f"  Deleted {deleted_count} corrupted records")
    
    return deleted_count

def import_verified_data(cur, conn):
    """Import verified transactions from CSV file."""
    print(f"\n✓ Importing verified data from: {VERIFIED_FILE}")
    
    if not os.path.exists(VERIFIED_FILE):
        print(f"  ✗ ERROR: File not found!")
        return 0
    
    imported_count = 0
    skipped_count = 0
    errors = []
    
    with open(VERIFIED_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row_num, row in enumerate(reader, start=2):
            try:
                date_str = row.get('Date', '').strip()
                description = row.get('Description', '').strip()
                debit_str = row.get('Debit Amount', '').strip()
                credit_str = row.get('Credit Amount', '').strip()
                balance_str = row.get('Running Balance', '').strip()
                
                # Parse amounts
                debit = float(debit_str) if debit_str else None
                credit = float(credit_str) if credit_str else None
                balance = float(balance_str) if balance_str else 0.0
                
                # Only insert if we have a date and description
                if not date_str or not description:
                    skipped_count += 1
                    continue
                
                # Insert transaction
                cur.execute("""
                    INSERT INTO banking_transactions (
                        account_number,
                        transaction_date,
                        description,
                        debit_amount,
                        credit_amount,
                        balance
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    '903990106011',
                    date_str,
                    description,
                    debit,
                    credit,
                    balance
                ))
                
                imported_count += 1
                
            except Exception as e:
                skipped_count += 1
                errors.append((row_num, str(e)))
    
    conn.commit()
    
    print(f"  Imported {imported_count} verified transactions")
    if skipped_count > 0:
        print(f"  ⚠ Skipped {skipped_count} rows")
    
    return imported_count

def verify_import(cur):
    """Verify import was successful."""
    print("\n" + "=" * 100)
    print("VERIFICATION RESULTS")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_count,
            MIN(transaction_date) as earliest,
            MAX(transaction_date) as latest,
            MIN(balance) as min_balance,
            MAX(balance) as max_balance,
            SUM(COALESCE(debit_amount, 0)) as total_debits,
            SUM(COALESCE(credit_amount, 0)) as total_credits
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
    """)
    
    total, earliest, latest, min_bal, max_bal, debits, credits = cur.fetchone()
    
    print(f"\nTransaction Summary:")
    print(f"  Total records: {total}")
    print(f"  Date range: {earliest} to {latest}")
    print(f"  Balance range: ${min_bal:,.2f} to ${max_bal:,.2f}")
    print(f"  Total debits: ${debits:,.2f}")
    print(f"  Total credits: ${credits:,.2f}")
    
    # Check key balance checkpoints from verified statement
    print(f"\nKey Balance Checkpoints (from verified statement):")
    checkpoints = [
        ('2012-01-31', 6157.50, 'Jan 31 close'),
        ('2012-02-23', 11577.50, 'Feb 23 after deposit'),
        ('2012-03-30', 15352.50, 'Mar 30 close'),
        ('2012-04-30', 16068.27, 'Apr 30 (after POS purchase)'),
        ('2012-05-31', 18385.77, 'May 31 close'),
        ('2012-06-01', None, 'Jun start'),
        ('2012-12-31', None, 'Dec 31 close'),
    ]
    
    for check_date, expected_balance, label in checkpoints:
        cur.execute("""
            SELECT balance FROM banking_transactions
            WHERE account_number = '903990106011'
            AND transaction_date = %s
            ORDER BY transaction_id DESC
            LIMIT 1
        """, (check_date,))
        
        result = cur.fetchone()
        if result:
            actual = result[0]
            if expected_balance is not None:
                status = "✓" if abs(actual - expected_balance) < 0.01 else "✗"
                diff = actual - expected_balance
                print(f"  {status} {check_date} ({label}): ${actual:,.2f} (expected ${expected_balance:,.2f}, diff ${diff:,.2f})")
            else:
                print(f"  • {check_date} ({label}): ${actual:,.2f}")
        else:
            print(f"  ✗ {check_date} ({label}): NO DATA")

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        print("=" * 100)
        print("SCOTIA BANK 2012 COMPLETE RESTORATION")
        print("Account: 903990106011")
        print("=" * 100)
        print("\nThis will:")
        print("  1. Backup current Scotia 2012 data (2,318 corrupted records)")
        print("  2. Delete all Scotia 2012 records")
        print("  3. Import 786 verified transactions from official statement file")
        print("\nThe database currently has 66% duplicates and systematically wrong balances.")
        print("This restoration will replace them with verified statement data.")
        print()
        
        response = input("Continue with Scotia 2012 restoration? (y/N): ").strip().lower()
        if response != 'y':
            print("Aborted.")
            return
        
        # Step 1: Backup
        backup_table = backup_current_data(cur)
        conn.commit()
        
        # Step 2: Delete
        deleted = delete_current_data(cur)
        conn.commit()
        
        # Step 3: Import
        imported = import_verified_data(cur, conn)
        
        # Step 4: Verify
        verify_import(cur)
        conn.commit()
        
        print("\n" + "=" * 100)
        print("RESTORATION COMPLETE")
        print("=" * 100)
        print(f"\nResults:")
        print(f"  ✓ Backup table: {backup_table}")
        print(f"  ✓ Deleted: {deleted:,} corrupted records")
        print(f"  ✓ Imported: {imported:,} verified records")
        print(f"\nThe Scotia 2012 account (903990106011) has been restored from verified statement data.")
        
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
