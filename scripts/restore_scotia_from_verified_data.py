#!/usr/bin/env python
"""
Restore Scotia 2012 from the VERIFIED scotiabank verified data.csv file.

This is the authoritative file with correct balances:
- Opening: $40.00 (Jan 1)
- Closing: $952.04 (Dec 31)
- Total debits: $51,004.12
- Total credits: $51,950.93
"""
import psycopg2
import csv
import os
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

VERIFIED_FILE = r"L:\limo\CIBC UPLOADS\scotiabank verified data.csv"
ACCOUNT_NUMBER = "903990106011"

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
            # Parse row
            # Columns: Transaction ID, Date, Description, Debit, Credit, Balance
            
            try:
                txn_id = row.get('Transaction ID', '').strip() or None
                date_str = row.get('Date', '').strip()
                description = row.get('Description', '').strip()
                debit_str = row.get('Debit', '').strip()
                credit_str = row.get('Credit', '').strip()
                balance_str = row.get('Balance', '').strip()
                
                # Skip empty rows
                if not date_str:
                    continue
                
                # Parse date - it's in format "40961" which is days since 1900 (Excel serial date)
                try:
                    date_int = int(date_str)
                    # Excel serial date: 40961 = ~2012-03-31
                    # Formula: date = datetime(1900, 1, 1) + timedelta(days=date_int-2)
                    from datetime import datetime, timedelta
                    date_obj = datetime(1900, 1, 1) + timedelta(days=date_int - 2)
                    date_str = date_obj.strftime('%Y-%m-%d')
                except:
                    # If it fails, try parsing as regular date
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
                    'txn_id': txn_id,
                    'date': date_str,
                    'description': description,
                    'debit': debit_amount,
                    'credit': credit_amount,
                    'balance': balance
                })
            except Exception as e:
                print(f"  ⚠ Error parsing row: {row}")
                print(f"    Error: {e}")
                continue
    
    print(f"✓ Parsed {len(transactions):,} transactions from verified file")
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
        print(f"✓ Deleted {deleted_count:,} corrupted records")
    return deleted_count

def import_verified_transactions(transactions):
    """Import verified transactions into database."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print(f"\nImporting {len(transactions):,} verified transactions...")
    
    imported_count = 0
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
                txn['balance']
            ))
            imported_count += 1
            
            if (i + 1) % 100 == 0:
                print(f"  {i + 1:,}/{len(transactions):,} transactions imported...")
        except Exception as e:
            print(f"  ⚠ Error importing transaction {i}: {txn}")
            print(f"    Error: {e}")
            continue
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"✓ Successfully imported {imported_count:,} transactions")
    return imported_count

def verify_import():
    """Verify the imported data matches verified statement totals."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "=" * 100)
    print("VERIFICATION AGAINST VERIFIED STATEMENT")
    print("=" * 100)
    
    # Get first and last balance
    cur.execute("""
        SELECT balance FROM banking_transactions
        WHERE account_number = %s
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        ORDER BY transaction_date, transaction_id LIMIT 1
    """, (ACCOUNT_NUMBER,))
    first_bal = cur.fetchone()
    first_bal = float(first_bal[0]) if first_bal else None
    
    cur.execute("""
        SELECT balance FROM banking_transactions
        WHERE account_number = %s
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        ORDER BY transaction_date DESC, transaction_id DESC LIMIT 1
    """, (ACCOUNT_NUMBER,))
    last_bal = cur.fetchone()
    last_bal = float(last_bal[0]) if last_bal else None
    
    # Get totals
    cur.execute("""
        SELECT 
            COUNT(*) as txn_count,
            COALESCE(SUM(COALESCE(debit_amount, 0)), 0) as total_debits,
            COALESCE(SUM(COALESCE(credit_amount, 0)), 0) as total_credits
        FROM banking_transactions
        WHERE account_number = %s
        AND EXTRACT(YEAR FROM transaction_date) = 2012
    """, (ACCOUNT_NUMBER,))
    
    txn_count, debits, credits = cur.fetchone()
    debits = float(debits)
    credits = float(credits)
    
    print(f"\nDatabase State:")
    print(f"  Transactions: {txn_count:,}")
    print(f"  Opening balance: ${first_bal:,.2f}")
    print(f"  Closing balance: ${last_bal:,.2f}")
    print(f"  Total debits: ${debits:,.2f}")
    print(f"  Total credits: ${credits:,.2f}")
    
    print(f"\nVerified Statement:")
    print(f"  Opening balance: $40.00")
    print(f"  Closing balance: $952.04")
    print(f"  Total debits: $51,004.12")
    print(f"  Total credits: $51,950.93")
    
    print(f"\nMatches:")
    opening_ok = abs(first_bal - 40.00) < 0.01 if first_bal else False
    closing_ok = abs(last_bal - 952.04) < 0.01 if last_bal else False
    debits_ok = abs(debits - 51004.12) < 1.00
    credits_ok = abs(credits - 51950.93) < 1.00
    
    print(f"  {'✓' if opening_ok else '✗'} Opening balance matches ($40.00)")
    print(f"  {'✓' if closing_ok else '✗'} Closing balance matches ($952.04)")
    print(f"  {'✓' if debits_ok else '✗'} Total debits match ($51,004.12)")
    print(f"  {'✓' if credits_ok else '✗'} Total credits match ($51,950.93)")
    
    if opening_ok and closing_ok and debits_ok and credits_ok:
        print(f"\n✓ RESTORATION SUCCESSFUL - All verified statement totals match!")
    else:
        print(f"\n⚠ Some totals do not match. Verify source file.")
    
    cur.close()
    conn.close()

def main():
    print("\n" + "=" * 100)
    print("SCOTIA 2012 RESTORATION FROM VERIFIED FILE")
    print("=" * 100)
    
    # Step 1: Parse verified file
    transactions = parse_verified_file()
    
    # Step 2: Backup current data
    backup_table = backup_current_data()
    
    # Step 3: Ask for confirmation
    print(f"\nAbout to:")
    print(f"  1. Delete {len(transactions)} records from account {ACCOUNT_NUMBER}")
    print(f"  2. Import {len(transactions):,} verified transactions from {VERIFIED_FILE}")
    
    response = input(f"\nProceed? (y/N): ").strip().lower()
    if response != 'y':
        print("Aborted.")
        return
    
    # Step 4: Delete old data
    delete_current_data()
    
    # Step 5: Import verified transactions
    import_verified_transactions(transactions)
    
    # Step 6: Verify
    verify_import()

if __name__ == '__main__':
    main()
