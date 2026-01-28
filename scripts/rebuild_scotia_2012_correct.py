#!/usr/bin/env python
"""
Rebuild Scotia 2012 with CORRECT data.

User-verified statement checkpoints:
- Jan 1, 2012: $40.00 (opening)
- Apr 30, 2012: $266.00
- May 31, 2012: $1,069.27
- Jun 29, 2012: $4,195.89
- Jul 31, 2012: $8,000.21
- Aug 31, 2012: $591.06
- Sep 28, 2012: $3,122.29
- Oct 31, 2012: $430.21
- Nov 30, 2012: $5.23
- Dec 31, 2012: $952.04 (closing)

Total debits: $51,004.12
Total credits: $51,950.93
"""
import psycopg2
import csv
import os
from datetime import datetime, timedelta

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

VERIFIED_FILE = r"L:\limo\CIBC UPLOADS\scotiabank verified data.csv"
ACCOUNT_NUMBER = "903990106011"

# User-provided verified checkpoints
VERIFIED_CHECKPOINTS = {
    '2012-01-01': 40.00,
    '2012-04-30': 266.00,
    '2012-05-31': 1069.27,
    '2012-06-29': 4195.89,
    '2012-07-31': 8000.21,
    '2012-08-31': 591.06,
    '2012-09-28': 3122.29,
    '2012-10-31': 430.21,
    '2012-11-30': 5.23,
    '2012-12-31': 952.04
}

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def parse_verified_file():
    """Parse the verified scotiabank verified data.csv file."""
    transactions = []
    
    print(f"Reading verified file: {VERIFIED_FILE}")
    
    with open(VERIFIED_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                date_str = row.get('Date', '').strip()
                description = row.get('Description', '').strip()
                debit_str = row.get('Debit', '').strip()
                credit_str = row.get('Credit', '').strip()
                balance_str = row.get('Balance', '').strip()
                
                # Skip empty rows
                if not date_str:
                    continue
                
                # Parse date from Excel serial number
                try:
                    date_int = int(date_str)
                    date_obj = datetime(1900, 1, 1) + timedelta(days=date_int - 2)
                    date_str = date_obj.strftime('%Y-%m-%d')
                except:
                    try:
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        date_str = date_obj.strftime('%Y-%m-%d')
                    except:
                        print(f"  ⚠ Skipping row with unparseable date: {date_str}")
                        continue
                
                # Only include 2012 transactions
                if not date_str.startswith('2012'):
                    continue
                
                # Parse amounts
                debit_amount = float(debit_str) if debit_str else 0.0
                credit_amount = float(credit_str) if credit_str else 0.0
                balance = float(balance_str) if balance_str else 0.0
                
                transactions.append({
                    'date': date_str,
                    'description': description,
                    'debit': debit_amount,
                    'credit': credit_amount,
                    'verified_balance': balance  # Balance from verified file
                })
            except Exception as e:
                print(f"  ⚠ Error parsing row: {row}")
                continue
    
    print(f"✓ Parsed {len(transactions):,} transactions from verified file")
    return transactions

def recalculate_balances(transactions):
    """Recalculate all balances from Jan 1 opening of $40."""
    print(f"\nRecalculating balances from opening balance of $40.00...")
    
    opening_balance = 40.00
    running_balance = opening_balance
    
    # Sort transactions by date
    transactions.sort(key=lambda x: (x['date'], x['description']))
    
    for txn in transactions:
        # Apply debit (subtract)
        if txn['debit'] > 0:
            running_balance -= txn['debit']
        # Apply credit (add)
        if txn['credit'] > 0:
            running_balance += txn['credit']
        
        txn['calculated_balance'] = round(running_balance, 2)
    
    return transactions

def backup_current_data():
    """Create backup of current Scotia data."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check current count
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions
        WHERE account_number = %s
        AND EXTRACT(YEAR FROM transaction_date) = 2012
    """, (ACCOUNT_NUMBER,))
    count = cur.fetchone()[0]
    
    if count > 0:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_table = f'banking_transactions_scotia_2012_backup_{timestamp}'
        
        print(f"\nCreating backup table: {backup_table}")
        cur.execute(f"""
            CREATE TABLE {backup_table} AS
            SELECT * FROM banking_transactions
            WHERE account_number = %s
            AND EXTRACT(YEAR FROM transaction_date) = 2012
        """, (ACCOUNT_NUMBER,))
        
        print(f"✓ Backup created with {count:,} records")
        conn.commit()
        cur.close()
        conn.close()
        return backup_table
    else:
        cur.close()
        conn.close()
        return None

def delete_current_data():
    """Delete current Scotia 2012 data."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        DELETE FROM banking_transactions
        WHERE account_number = %s
        AND EXTRACT(YEAR FROM transaction_date) = 2012
    """, (ACCOUNT_NUMBER,))
    
    deleted_count = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    
    if deleted_count > 0:
        print(f"✓ Deleted {deleted_count:,} records from production")
    return deleted_count

def import_transactions(transactions):
    """Import transactions with recalculated balances."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print(f"\nImporting {len(transactions):,} transactions...")
    
    # Add opening balance entry
    cur.execute("""
        INSERT INTO banking_transactions (
            account_number, transaction_date, description,
            debit_amount, credit_amount, balance
        ) VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        ACCOUNT_NUMBER,
        '2012-01-01',
        'Opening balance',
        0.0,
        0.0,
        40.00
    ))
    
    # Import all transactions
    for i, txn in enumerate(transactions):
        try:
            cur.execute("""
                INSERT INTO banking_transactions (
                    account_number, transaction_date, description,
                    debit_amount, credit_amount, balance
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                ACCOUNT_NUMBER,
                txn['date'],
                txn['description'],
                txn['debit'],
                txn['credit'],
                txn['calculated_balance']
            ))
            
            if (i + 1) % 100 == 0:
                print(f"  {i + 1:,}/{len(transactions):,} transactions imported...")
        except Exception as e:
            print(f"  ⚠ Error importing transaction {i}: {txn}")
            continue
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"✓ Successfully imported {len(transactions):,} transactions + opening balance")

def verify_against_checkpoints():
    """Verify database matches user-verified checkpoints."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "=" * 100)
    print("VERIFICATION AGAINST USER-PROVIDED CHECKPOINTS")
    print("=" * 100)
    
    checkpoints_passed = 0
    checkpoints_failed = 0
    
    for checkpoint_date, expected_balance in sorted(VERIFIED_CHECKPOINTS.items()):
        # Find closest transaction on or before this date
        cur.execute("""
            SELECT balance FROM banking_transactions
            WHERE account_number = %s
            AND transaction_date <= %s
            ORDER BY transaction_date DESC, transaction_id DESC
            LIMIT 1
        """, (ACCOUNT_NUMBER, checkpoint_date))
        
        result = cur.fetchone()
        actual_balance = float(result[0]) if result else None
        
        if actual_balance is None:
            print(f"  ✗ {checkpoint_date}: NO DATA (expected: ${expected_balance:,.2f})")
            checkpoints_failed += 1
        elif abs(actual_balance - expected_balance) < 0.01:
            print(f"  ✓ {checkpoint_date}: ${actual_balance:,.2f} ✓ MATCH")
            checkpoints_passed += 1
        else:
            diff = actual_balance - expected_balance
            print(f"  ✗ {checkpoint_date}: ${actual_balance:,.2f} vs ${expected_balance:,.2f} (diff: ${diff:+,.2f})")
            checkpoints_failed += 1
    
    print(f"\nCheckpoint Results: {checkpoints_passed} passed, {checkpoints_failed} failed")
    
    if checkpoints_failed == 0:
        print(f"✓ ALL CHECKPOINTS VERIFIED!")
    
    cur.close()
    conn.close()
    
    return checkpoints_passed, checkpoints_failed

def main():
    print("\n" + "=" * 100)
    print("SCOTIA 2012 REBUILD WITH VERIFIED CHECKPOINTS")
    print("=" * 100)
    
    # Step 1: Parse file
    transactions = parse_verified_file()
    
    # Step 2: Recalculate balances
    transactions = recalculate_balances(transactions)
    
    # Step 3: Backup
    backup_current_data()
    
    # Step 4: Ask for confirmation
    print(f"\nAbout to:")
    print(f"  1. Delete current Scotia 2012 data from {ACCOUNT_NUMBER}")
    print(f"  2. Import {len(transactions):,} verified transactions")
    print(f"  3. Recalculate all balances from opening: $40.00")
    print(f"  4. Verify against {len(VERIFIED_CHECKPOINTS)} checkpoint dates")
    
    response = input(f"\nProceed? (y/N): ").strip().lower()
    if response != 'y':
        print("Aborted.")
        return
    
    # Step 5: Delete and import
    delete_current_data()
    import_transactions(transactions)
    
    # Step 6: Verify
    verify_against_checkpoints()

if __name__ == '__main__':
    main()
