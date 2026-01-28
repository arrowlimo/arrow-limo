"""
Import verified 2012 CIBC statement data into banking_transactions table.
Replaces existing 2012 data for account 0228362 with penny-perfect verified data.

Account: 00339 74-61615 (CIBC checking)
Period: January 1 - December 31, 2012
Source: l:\limo\reports\2012_cibc_complete_running_balance_verification.md
"""

import os
import sys
import psycopg2
import re
from datetime import datetime
import hashlib

def get_db_connection():
    """Get PostgreSQL connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def parse_verification_file():
    """Parse the verification markdown file and extract all transactions."""
    transactions = []
    
    with open(r'l:\limo\reports\2012_cibc_complete_running_balance_verification.md', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    current_date = None
    for line in lines:
        # Skip non-transaction lines
        if not line.startswith('| Jan ') and not line.startswith('| Feb ') and \
           not line.startswith('| Mar ') and not line.startswith('| Apr ') and \
           not line.startswith('| May ') and not line.startswith('| Jun ') and \
           not line.startswith('| Jul ') and not line.startswith('| Aug ') and \
           not line.startswith('| Sep ') and not line.startswith('| Oct ') and \
           not line.startswith('| Nov ') and not line.startswith('| Dec '):
            continue
        
        parts = line.split('|')
        if len(parts) < 8:
            continue
        
        date_str = parts[1].strip()
        description = parts[2].strip()
        trans_type = parts[3].strip()
        amount_str = parts[4].strip()
        balance_str = parts[7].strip()
        
        # Skip header rows, balance forward rows, opening/closing balance rows
        if amount_str == 'Amount' or amount_str == '-' or 'balance' in description.lower():
            continue
        
        # Skip non-transaction rows
        if trans_type not in ['D', 'W']:
            continue
        
        try:
            # Parse date
            month_day = date_str.split()
            if len(month_day) != 2:
                continue
            
            month_str, day_str = month_day
            month_map = {
                'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
            }
            
            month = month_map.get(month_str)
            if not month:
                continue
            
            day = int(day_str)
            trans_date = f'2012-{month:02d}-{day:02d}'
            
            # Parse amount
            amount = float(amount_str.replace(',', ''))
            
            # Parse balance
            balance = float(balance_str.replace(',', ''))
            
            # Determine debit/credit
            if trans_type == 'W':  # Withdrawal
                debit_amount = amount
                credit_amount = None
            else:  # Deposit
                debit_amount = None
                credit_amount = amount
            
            # Create transaction hash for idempotency
            hash_string = f"{trans_date}|{description}|{debit_amount}|{credit_amount}|{balance}"
            transaction_hash = hashlib.sha256(hash_string.encode()).hexdigest()
            
            transactions.append({
                'date': trans_date,
                'description': description,
                'debit': debit_amount,
                'credit': credit_amount,
                'balance': balance,
                'hash': transaction_hash
            })
            
        except (ValueError, IndexError) as e:
            # Skip malformed lines
            continue
    
    return transactions

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Step 1: Parse verification file
        print("📄 Parsing verification file...")
        transactions = parse_verification_file()
        print(f"   Found {len(transactions)} verified transactions")
        
        if len(transactions) == 0:
            print("[FAIL] No transactions found in verification file!")
            return
        
        # Step 2: Create backup of existing 2012 data
        backup_table = f"banking_transactions_2012_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"\n💾 Creating backup: {backup_table}")
        cur.execute(f"""
            CREATE TABLE {backup_table} AS
            SELECT * FROM banking_transactions
            WHERE account_number = '0228362'
            AND transaction_date >= '2012-01-01'
            AND transaction_date <= '2012-12-31'
        """)
        backup_count = cur.rowcount
        print(f"   Backed up {backup_count} existing 2012 transactions")
        
        # Step 3: Remove foreign key references
        print(f"\n🔗 Removing foreign key references...")
        
        # Remove from banking_payment_links
        cur.execute("""
            DELETE FROM banking_payment_links
            WHERE banking_transaction_id IN (
                SELECT transaction_id FROM banking_transactions
                WHERE account_number = '0228362'
                AND transaction_date >= '2012-01-01'
                AND transaction_date <= '2012-12-31'
            )
        """)
        links_deleted = cur.rowcount
        print(f"   Removed {links_deleted} banking_payment_links")
        
        # Clear banking_transaction_id from payments table
        cur.execute("""
            UPDATE payments
            SET banking_transaction_id = NULL
            WHERE banking_transaction_id IN (
                SELECT transaction_id FROM banking_transactions
                WHERE account_number = '0228362'
                AND transaction_date >= '2012-01-01'
                AND transaction_date <= '2012-12-31'
            )
        """)
        payments_unlinked = cur.rowcount
        print(f"   Unlinked {payments_unlinked} payments")
        
        # Step 4: Delete existing 2012 data for this account
        print(f"\n🗑️  Deleting existing 2012 data for account 0228362...")
        cur.execute("""
            DELETE FROM banking_transactions
            WHERE account_number = '0228362'
            AND transaction_date >= '2012-01-01'
            AND transaction_date <= '2012-12-31'
        """)
        deleted_count = cur.rowcount
        print(f"   Deleted {deleted_count} existing records")
        
        # Step 5: Insert verified data
        print(f"\n[OK] Inserting {len(transactions)} verified transactions...")
        
        inserted = 0
        for trans in transactions:
            cur.execute("""
                INSERT INTO banking_transactions (
                    account_number,
                    transaction_date,
                    description,
                    debit_amount,
                    credit_amount,
                    balance,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """, (
                '0228362',  # CIBC checking account
                trans['date'],
                trans['description'],
                trans['debit'],
                trans['credit'],
                trans['balance']
            ))
            inserted += 1
            
            if inserted % 100 == 0:
                print(f"   Progress: {inserted}/{len(transactions)}")
        
        conn.commit()
        
        # Step 6: Verify import
        print(f"\n🔍 Verifying import...")
        cur.execute("""
            SELECT 
                COUNT(*) as count,
                MIN(transaction_date) as first_date,
                MAX(transaction_date) as last_date,
                SUM(COALESCE(debit_amount, 0)) as total_debits,
                SUM(COALESCE(credit_amount, 0)) as total_credits
            FROM banking_transactions
            WHERE account_number = '0228362'
            AND transaction_date >= '2012-01-01'
            AND transaction_date <= '2012-12-31'
        """)
        
        result = cur.fetchone()
        count, first_date, last_date, total_debits, total_credits = result
        
        print(f"\n" + "="*60)
        print(f"[OK] IMPORT COMPLETE")
        print(f"="*60)
        print(f"Account: 0228362 (CIBC 00339 74-61615)")
        print(f"Period: {first_date} to {last_date}")
        print(f"Transactions: {count}")
        print(f"Total Debits: ${total_debits:,.2f}")
        print(f"Total Credits: ${total_credits:,.2f}")
        print(f"Net: ${total_credits - total_debits:,.2f}")
        print(f"\nBackup table: {backup_table}")
        print(f"Backed up records: {backup_count}")
        print(f"="*60)
        
    except Exception as e:
        conn.rollback()
        print(f"\n[FAIL] ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    print("="*60)
    print("2012 CIBC Verified Data Import")
    print("="*60)
    print("\n[WARN]  This will:")
    print("  1. Backup existing 2012 data for account 0228362")
    print("  2. Delete existing 2012 data for account 0228362")
    print("  3. Import verified data from verification file")
    print()
    
    response = input("Continue? (yes/no): ").strip().lower()
    if response != 'yes':
        print("[FAIL] Aborted")
        sys.exit(0)
    
    main()
