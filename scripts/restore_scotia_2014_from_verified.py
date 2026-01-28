#!/usr/bin/env python
"""
Restore Scotia 2014 (account 903990106011) from verified statement data.
User confirmed: Starting balance $1,839.42, Ending balance $4,006.29
"""
import psycopg2
import csv
from datetime import datetime
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

# User can provide verified 2014 file path here
VERIFIED_FILE = r"L:\limo\data\scotia_2014_verified.csv"  # Update this path

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def backup_and_delete_2014(cur, conn):
    """Backup and delete current Scotia 2014 data."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'banking_transactions_scotia_2014_backup_{timestamp}'
    
    print(f"Creating backup: {backup_table}")
    cur.execute(f"""
        CREATE TABLE {backup_table} AS
        SELECT * FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2014
    """)
    
    cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
    backup_count = cur.fetchone()[0]
    print(f"✓ Backed up {backup_count} records")
    
    cur.execute("""
        DELETE FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2014
    """)
    
    deleted = cur.rowcount
    print(f"✓ Deleted {deleted} corrupted records")
    conn.commit()
    
    return backup_table, deleted

def import_verified_2014(cur, conn):
    """Import verified 2014 transactions."""
    
    if not os.path.exists(VERIFIED_FILE):
        print(f"\n✗ File not found: {VERIFIED_FILE}")
        print("\nPlease provide the verified 2014 CSV file with columns:")
        print("  date, description, debit, credit, balance")
        print(f"\nSave it as: {VERIFIED_FILE}")
        return 0
    
    print(f"\nImporting from: {VERIFIED_FILE}")
    
    imported = 0
    errors = []
    
    with open(VERIFIED_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row_num, row in enumerate(reader, start=2):
            try:
                date = row['date'].strip()
                description = row['description'].strip()
                debit_str = row.get('debit', '').strip()
                credit_str = row.get('credit', '').strip()
                balance_str = row.get('balance', '').strip()
                
                debit = float(debit_str) if debit_str else None
                credit = float(credit_str) if credit_str else None
                balance = float(balance_str.replace('$', '').replace(',', '')) if balance_str else None
                
                cur.execute("""
                    INSERT INTO banking_transactions (
                        account_number, transaction_date, description,
                        debit_amount, credit_amount, balance
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, ('903990106011', date, description, debit, credit, balance))
                
                imported += 1
                
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
    
    conn.commit()
    print(f"✓ Imported {imported} transactions")
    
    if errors:
        print(f"\n⚠ {len(errors)} errors:")
        for err in errors[:5]:
            print(f"  {err}")
    
    return imported

def verify_2014(cur):
    """Verify 2014 data matches expected balances."""
    print("\n" + "=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as cnt,
            MIN(transaction_date) as first,
            MAX(transaction_date) as last,
            MIN(balance) as min_bal,
            MAX(balance) as max_bal
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2014
    """)
    
    cnt, first, last, min_bal, max_bal = cur.fetchone()
    
    print(f"Transactions: {cnt}")
    print(f"Date range: {first} to {last}")
    print(f"Balance range: ${min_bal:.2f} to ${max_bal:.2f}")
    
    # Check opening balance
    cur.execute("""
        SELECT balance FROM banking_transactions
        WHERE account_number = '903990106011'
        AND transaction_date = '2014-01-01'
        ORDER BY transaction_id
        LIMIT 1
    """)
    
    opening = cur.fetchone()
    if opening:
        expected_opening = 1839.42
        actual = opening[0]
        status = "✓" if abs(actual - expected_opening) < 0.01 else "✗"
        print(f"\n{status} Opening balance (2014-01-01): ${actual:.2f} (expected ${expected_opening:.2f})")
    
    # Check closing balance
    cur.execute("""
        SELECT balance FROM banking_transactions
        WHERE account_number = '903990106011'
        AND transaction_date = '2014-12-31'
        ORDER BY transaction_id DESC
        LIMIT 1
    """)
    
    closing = cur.fetchone()
    if closing:
        expected_closing = 4006.29
        actual = closing[0]
        status = "✓" if abs(actual - expected_closing) < 0.01 else "✗"
        print(f"{status} Closing balance (2014-12-31): ${actual:.2f} (expected ${expected_closing:.2f})")

def main():
    print("=" * 80)
    print("SCOTIA 2014 DATA RESTORATION")
    print("=" * 80)
    print("\nExpected: Opening $1,839.42 → Closing $4,006.29")
    
    if not os.path.exists(VERIFIED_FILE):
        print(f"\n⚠ Verified data file not found: {VERIFIED_FILE}")
        print("\nPlease create this CSV file with your verified 2014 transactions.")
        print("Format: date,description,debit,credit,balance")
        return
    
    response = input("\nContinue with restoration? (y/N): ").strip().lower()
    if response != 'y':
        print("Aborted.")
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        backup_table, deleted = backup_and_delete_2014(cur, conn)
        imported = import_verified_2014(cur, conn)
        verify_2014(cur)
        
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Backup: {backup_table}")
        print(f"Deleted: {deleted} records")
        print(f"Imported: {imported} verified records")
        
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
