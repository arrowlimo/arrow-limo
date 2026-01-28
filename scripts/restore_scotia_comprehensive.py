#!/usr/bin/env python
"""
COMPREHENSIVE SCOTIA RESTORATION: 2012, 2013, 2014

User-confirmed balances:
- 2012: Opening $40.00 → Closing $952.04
- 2013: Opening $952.04 → Closing $6,404.87  
- 2014: Opening $1,839.42 → Closing $4,006.29

Current database has massive corruption (2,318 records for 2012 alone vs ~700 verified).
This script replaces ALL Scotia data for specified years with verified statement data.
"""
import psycopg2
import csv
from datetime import datetime
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

# Verified data files
FILES = {
    2012: r"L:\limo\reports\Scotia_Bank_2012_Full_Report.csv",
    2013: r"L:\limo\reports\Scotia_Bank_2013_Full_Report.csv",  # User to provide
    2014: r"L:\limo\reports\Scotia_Bank_2014_Full_Report.csv",  # User to provide
}

# Expected balances for verification
EXPECTED = {
    2012: {'open': 40.00, 'close': 952.04},
    2013: {'open': 952.04, 'close': 6404.87},
    2014: {'open': 1839.42, 'close': 4006.29},
}

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def backup_year(cur, conn, year):
    """Create timestamped backup for specified year."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'banking_transactions_scotia_{year}_backup_{timestamp}'
    
    print(f"Creating backup: {backup_table}")
    cur.execute(f"""
        CREATE TABLE {backup_table} AS
        SELECT * FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = {year}
    """)
    
    cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
    count = cur.fetchone()[0]
    print(f"  ✓ Backed up {count} records")
    conn.commit()
    
    return backup_table, count

def delete_year(cur, conn, year):
    """Delete all Scotia records for specified year."""
    cur.execute("""
        DELETE FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = %s
    """, (year,))
    
    deleted = cur.rowcount
    print(f"  ✓ Deleted {deleted} corrupted records")
    conn.commit()
    
    return deleted

def import_verified_year(cur, conn, year, filename):
    """Import verified transactions from CSV."""
    if not os.path.exists(filename):
        print(f"  ✗ File not found: {filename}")
        print(f"    Please create this file with verified {year} data")
        return 0
    
    print(f"  Importing from: {os.path.basename(filename)}")
    
    imported = 0
    errors = []
    
    with open(filename, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row_num, row in enumerate(reader, start=2):
            try:
                # Handle various date column names
                date = (row.get('Date') or row.get('date') or row.get('transaction_date') or '').strip()
                
                # Handle various description column names
                description = (row.get('Description') or row.get('description') or '').strip()
                
                # Handle various amount column names (with spaces)
                debit_str = (row.get('Debit Amount') or row.get('Debit') or row.get('debit') or 
                           row.get('Withdrawal') or row.get('debit_amount') or '').strip()
                credit_str = (row.get('Credit Amount') or row.get('Credit') or row.get('credit') or 
                            row.get('Deposit') or row.get('credit_amount') or '').strip()
                balance_str = (row.get('Running Balance') or row.get('Balance') or row.get('balance') or '').strip()
                
                # Parse amounts
                debit = float(debit_str.replace('$', '').replace(',', '')) if debit_str else None
                credit = float(credit_str.replace('$', '').replace(',', '')) if credit_str else None
                balance = float(balance_str.replace('$', '').replace(',', '')) if balance_str else None
                
                if not date or date == 'Date':  # Skip header row if present
                    continue
                
                # Insert
                cur.execute("""
                    INSERT INTO banking_transactions (
                        account_number, transaction_date, description,
                        debit_amount, credit_amount, balance
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, ('903990106011', date, description, debit, credit, balance))
                
                imported += 1
                
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
                if len(errors) > 10:
                    break
    
    conn.commit()
    print(f"  ✓ Imported {imported} transactions")
    
    if errors:
        print(f"  ⚠ {len(errors)} errors:")
        for err in errors[:5]:
            print(f"    {err}")
    
    return imported

def verify_year(cur, year):
    """Verify balances match expected values."""
    expected = EXPECTED[year]
    
    # Get first transaction with balance
    cur.execute("""
        SELECT transaction_date, balance FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = %s
        AND balance IS NOT NULL
        ORDER BY transaction_date, transaction_id
        LIMIT 1
    """, (year,))
    
    opening = cur.fetchone()
    if opening and opening[1] is not None:
        actual_open = float(opening[1])
        open_ok = abs(actual_open - expected['open']) < 0.01
        print(f"  {'✓' if open_ok else '✗'} First balance ({opening[0]}): ${actual_open:.2f} (expected ~${expected['open']:.2f})")
    else:
        print(f"  ✗ No opening balance found for {year}")
    
    # Get last transaction with balance
    cur.execute("""
        SELECT transaction_date, balance FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = %s
        AND balance IS NOT NULL
        ORDER BY transaction_date DESC, transaction_id DESC
        LIMIT 1
    """, (year,))
    
    closing = cur.fetchone()
    if closing and closing[1] is not None:
        actual_close = float(closing[1])
        close_ok = abs(actual_close - expected['close']) < 0.01
        print(f"  {'✓' if close_ok else '✗'} Last balance ({closing[0]}): ${actual_close:.2f} (expected ${expected['close']:.2f})")
        
        # Return closing balance for year-over-year check
        return actual_close
    else:
        print(f"  ⚠ No closing balance found for {year}")
        return None
    
    # Get record count
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = %s
    """, (year,))
    
    count = cur.fetchone()[0]
    print(f"  Total records: {count}")

def restore_year(conn, cur, year):
    """Complete restoration workflow for one year."""
    print("\n" + "=" * 80)
    print(f"SCOTIA {year} RESTORATION")
    print("=" * 80)
    
    # Check if file exists
    filename = FILES.get(year)
    if not filename or not os.path.exists(filename):
        print(f"✗ Verified file not available: {filename}")
        print(f"  Skipping {year} restoration")
        return
    
    # Step 1: Backup
    backup_table, backup_count = backup_year(cur, conn, year)
    
    # Step 2: Delete
    deleted = delete_year(cur, conn, year)
    
    # Step 3: Import
    imported = import_verified_year(cur, conn, year, filename)
    
    # Step 4: Verify
    print(f"\nVerification:")
    verify_year(cur, year)
    
    print(f"\nSummary:")
    print(f"  Backup: {backup_table}")
    print(f"  Deleted: {deleted} corrupted records")
    print(f"  Imported: {imported} verified records")
    print(f"  Reduction: {deleted - imported} records removed")

def main():
    print("=" * 80)
    print("SCOTIA COMPREHENSIVE RESTORATION (2012-2014)")
    print("=" * 80)
    
    # Check which files are available
    print("\nAvailable files:")
    for year, filename in FILES.items():
        exists = os.path.exists(filename) if filename else False
        status = "✓" if exists else "✗"
        print(f"  {status} {year}: {filename}")
    
    print("\nExpected balances:")
    for year, balances in EXPECTED.items():
        print(f"  {year}: ${balances['open']:.2f} → ${balances['close']:.2f}")
    
    response = input("\nContinue with restoration? (y/N): ").strip().lower()
    if response != 'y':
        print("Aborted.")
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Restore each year that has a verified file
        for year in sorted(FILES.keys()):
            restore_year(conn, cur, year)
        
        print("\n" + "=" * 80)
        print("RESTORATION COMPLETE")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        conn.rollback()
        raise
    
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
