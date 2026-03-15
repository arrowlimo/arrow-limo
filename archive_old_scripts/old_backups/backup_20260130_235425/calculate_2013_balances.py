"""Calculate and populate NULL balances for 2013 based on 2012 closing."""
import psycopg2
from decimal import Decimal
import sys

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***"
    )

def main():
    dry_run = '--write' not in sys.argv
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get 2012 closing balance
    cur.execute("""
        SELECT balance 
        FROM banking_transactions 
        WHERE account_number = '1615' 
        AND description = 'Closing balance'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
    """)
    result = cur.fetchone()
    if not result:
        print("❌ ERROR: 2012 closing balance not found!")
        conn.close()
        return
    
    starting_balance = Decimal(str(result[0]))
    print(f"2012 Closing Balance: ${starting_balance}")
    print(f"Using as 2013 Opening Balance: ${starting_balance}")
    print()
    
    # Get all 2013 transactions in order
    cur.execute("""
        SELECT transaction_id, transaction_date, description, 
               debit_amount, credit_amount, balance
        FROM banking_transactions 
        WHERE account_number = '1615' 
        AND EXTRACT(YEAR FROM transaction_date) = 2013
        ORDER BY transaction_date ASC, transaction_id ASC
    """)
    
    transactions = cur.fetchall()
    print(f"Found {len(transactions)} transactions for 2013")
    
    # Check if any already have balances
    with_balance = sum(1 for t in transactions if t[5] is not None)
    print(f"  {with_balance} with balance")
    print(f"  {len(transactions) - with_balance} with NULL balance")
    print()
    
    if with_balance > 0 and not dry_run:
        print("⚠️  WARNING: Some transactions already have balances!")
        response = input("Recalculate all? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            conn.close()
            return
    
    # Calculate running balances
    running_balance = starting_balance
    updates = []
    
    print("Calculating balances...")
    print("="*90)
    print(f"{'Date':<12} | {'Description':<35} | {'Debit':>10} | {'Credit':>10} | {'Balance':>12}")
    print("="*90)
    
    for txn in transactions[:10]:  # Show first 10 in preview
        txn_id, date, desc, debit, credit, old_balance = txn
        
        # Calculate new balance
        if debit:
            running_balance -= Decimal(str(debit))
        if credit:
            running_balance += Decimal(str(credit))
        
        debit_str = f"${debit:.2f}" if debit else "  --  "
        credit_str = f"${credit:.2f}" if credit else "  --  "
        print(f"{date} | {desc[:35]:<35} | {debit_str:>10} | {credit_str:>10} | ${running_balance:>11.2f}")
        
        updates.append((running_balance, txn_id))
    
    if len(transactions) > 10:
        print(f"... ({len(transactions) - 10} more transactions)")
        # Calculate the rest without printing
        for txn in transactions[10:]:
            txn_id, date, desc, debit, credit, old_balance = txn
            if debit:
                running_balance -= Decimal(str(debit))
            if credit:
                running_balance += Decimal(str(credit))
            updates.append((running_balance, txn_id))
    
    print("="*90)
    print(f"\nFinal 2013 Balance: ${running_balance:.2f}")
    
    if dry_run:
        print("\n🔍 DRY RUN - No changes made")
        print(f"Would update {len(updates)} transaction balances")
        print("\nRun with --write to apply changes")
    else:
        print(f"\n✍️  Updating {len(updates)} transaction balances...")
        
        # Create backup first
        cur.execute("""
            CREATE TABLE IF NOT EXISTS banking_transactions_1615_backup_2013 AS
            SELECT * FROM banking_transactions 
            WHERE account_number = '1615' 
            AND EXTRACT(YEAR FROM transaction_date) = 2013
        """)
        print("✅ Backup created: banking_transactions_1615_backup_2013")
        
        # Update balances
        for balance, txn_id in updates:
            cur.execute("""
                UPDATE banking_transactions 
                SET balance = %s 
                WHERE transaction_id = %s
            """, (balance, txn_id))
        
        conn.commit()
        print(f"✅ Updated {len(updates)} balances")
        print(f"✅ Final 2013 balance: ${running_balance:.2f}")
    
    conn.close()

if __name__ == '__main__':
    main()
