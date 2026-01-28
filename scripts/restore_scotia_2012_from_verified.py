#!/usr/bin/env python
"""
CRITICAL: Restore Scotia 2012 (account 903990106011) from verified statement data.
Current database contains 2,318 corrupted records vs 70-100 verified transactions.

This script:
1. Backs up current corrupted Scotia 2012 data
2. Deletes all Scotia 2012 records
3. Imports verified transactions from scotia_2012_manual_verified_part1.csv
4. Logs audit trail for CRA compliance
"""
import psycopg2
import csv
from datetime import datetime
import os
from pathlib import Path

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

VERIFIED_FILE = r"L:\limo\reports\scotia_2012_manual_verified_part1.csv"

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
    backup_table = f'banking_transactions_scotia_2012_backup_{timestamp}'
    
    print(f"Creating backup table: {backup_table}")
    cur.execute(f"""
        CREATE TABLE {backup_table} AS
        SELECT * FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
    """)
    
    cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
    backup_count = cur.fetchone()[0]
    print(f"✓ Backed up {backup_count} records to {backup_table}")
    
    return backup_table

def delete_current_data(cur):
    """Delete all Scotia 2012 records from banking_transactions."""
    print("\nDeleting current Scotia 2012 data from database...")
    
    cur.execute("""
        DELETE FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
    """)
    
    deleted_count = cur.rowcount
    print(f"✓ Deleted {deleted_count} corrupted records")
    
    return deleted_count

def import_verified_data(cur, conn):
    """Import verified transactions from CSV file."""
    print(f"\nImporting verified data from: {VERIFIED_FILE}")
    
    if not os.path.exists(VERIFIED_FILE):
        print(f"✗ ERROR: File not found: {VERIFIED_FILE}")
        return 0
    
    imported_count = 0
    skipped_count = 0
    errors = []
    
    with open(VERIFIED_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row_num, row in enumerate(reader, start=2):  # Skip header
            try:
                date_str = row.get('date', '').strip()
                description = row.get('description', '').strip()
                debit_str = row.get('debit', '').strip()
                credit_str = row.get('credit', '').strip()
                balance_str = row.get('balance', '').strip()
                
                # Parse amounts
                debit = float(debit_str) if debit_str and debit_str != '0' else None
                credit = float(credit_str) if credit_str and credit_str != '0' else None
                
                # Parse balance (remove $ if present)
                balance_clean = balance_str.replace('$', '').strip()
                balance = float(balance_clean) if balance_clean else 0
                
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
                errors.append(f"Row {row_num}: {str(e)}")
    
    conn.commit()
    
    print(f"✓ Imported {imported_count} verified transactions")
    if skipped_count > 0:
        print(f"⚠ Skipped {skipped_count} rows")
        for error in errors[:5]:  # Show first 5 errors
            print(f"  - {error}")
    
    return imported_count

def verify_import(cur):
    """Verify import was successful."""
    print("\n" + "=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    
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
    
    print(f"Total transactions: {total}")
    print(f"Date range: {earliest} to {latest}")
    print(f"Balance range: ${min_bal:.2f} to ${max_bal:.2f}")
    print(f"Total debits: ${debits:.2f}")
    print(f"Total credits: ${credits:.2f}")
    
    # Check key balance checkpoints
    print("\nBalance checkpoints:")
    checkpoints = [
        ('2012-01-01', 40.00),
        ('2012-02-29', 91.00),
        ('2012-04-30', 266.00),
        ('2012-05-18', 181.77),
        ('2012-06-22', 156.76),
        ('2012-06-25', 5317.51),
        ('2012-06-29', 4195.89),
    ]
    
    for check_date, expected_balance in checkpoints:
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
            status = "✓" if abs(actual - expected_balance) < 0.01 else "✗"
            print(f"  {status} {check_date}: ${actual:.2f} (expected ${expected_balance:.2f})")
        else:
            print(f"  ✗ {check_date}: NO DATA")

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        print("=" * 80)
        print("SCOTIA 2012 DATA RESTORATION")
        print("=" * 80)
        print()
        print("WARNING: This will DELETE all current Scotia 2012 banking data and replace it")
        print("with verified transactions from the statement file.")
        print()
        
        response = input("Continue? (y/N): ").strip().lower()
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
        
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Backed up:  {backup_table}")
        print(f"Deleted:    {deleted} corrupted records")
        print(f"Imported:   {imported} verified records")
        print(f"\nNote: This file contains only part of 2012 data.")
        print(f"Additional verified statement data must be extracted and imported.")
        
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
