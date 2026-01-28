"""
CORRECTED MASTER SCRIPT: Fill ONLY NULL balances for CIBC 1615 (2013-2017)
Do NOT recalculate existing balances.
2012 already has correct balances, so skip it.
"""
import psycopg2
from decimal import Decimal
import sys

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***"
    )

def fix_null_balances_for_year(cur, account_number, year, apply_fixes=False):
    """
    Calculate and fill ONLY NULL balance fields for a year.
    Do NOT modify existing non-NULL balances.
    """
    
    # Get all transactions for the year, ordered chronologically
    cur.execute("""
        SELECT transaction_id, transaction_date, description,
               debit_amount, credit_amount, balance
        FROM banking_transactions
        WHERE account_number = %s
        AND EXTRACT(YEAR FROM transaction_date) = %s
        ORDER BY transaction_date ASC, transaction_id ASC
    """, (account_number, year))
    
    transactions = cur.fetchall()
    if not transactions:
        return 0, None, [f"No transactions found for {year}"]
    
    # Find the first transaction with a known balance
    running_balance = None
    start_idx = 0
    
    for i, txn in enumerate(transactions):
        if txn[5] is not None:  # balance is not NULL
            running_balance = Decimal(str(txn[5]))
            start_idx = i + 1
            break
    
    if running_balance is None:
        # Try to get balance from previous year's closing
        prev_year = year - 1
        cur.execute("""
            SELECT balance FROM banking_transactions 
            WHERE account_number = %s 
            AND description IN ('Closing balance', 'Balance forward')
            AND EXTRACT(YEAR FROM transaction_date) = %s
            ORDER BY transaction_date DESC
            LIMIT 1
        """, (account_number, prev_year))
        result = cur.fetchone()
        if result:
            running_balance = Decimal(str(result[0]))
        else:
            return 0, None, [f"Cannot determine starting balance for {year}"]
    
    # Now calculate forward from the known point
    updates = []
    for txn in transactions[start_idx:]:
        txn_id, date, desc, debit, credit, old_balance = txn
        
        # Calculate new balance
        if debit:
            running_balance -= Decimal(str(debit))
        if credit:
            running_balance += Decimal(str(credit))
        
        # Only update if balance was NULL
        if old_balance is None:
            updates.append((running_balance, txn_id))
    
    # Apply updates if requested
    if apply_fixes:
        # Create backup first
        backup_table = f"banking_transactions_1615_backup_{year}"
        cur.execute(f"""
            DROP TABLE IF EXISTS {backup_table};
            CREATE TABLE {backup_table} AS
            SELECT * FROM banking_transactions 
            WHERE account_number = %s 
            AND EXTRACT(YEAR FROM transaction_date) = %s
        """, (account_number, year))
        
        # Apply all updates
        for balance, txn_id in updates:
            cur.execute("""
                UPDATE banking_transactions 
                SET balance = %s 
                WHERE transaction_id = %s
            """, (balance, txn_id))
    
    return len(updates), running_balance, []

def main():
    apply_fixes = '--write' in sys.argv
    account_number = '1615'
    years = [2013, 2014, 2015, 2016, 2017]  # 2012 already has correct balances
    
    print("="*100)
    print("CIBC 1615 NULL Balance Filler")
    print("="*100)
    print(f"Mode: {'WRITE (applying changes)' if apply_fixes else 'DRY-RUN (analyzing only)'}")
    print(f"Target: Fill NULL balances for years {years}")
    print()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    all_results = {}
    total_updates = 0
    
    # First pass: dry-run to preview
    for year in years:
        print(f"\n{year}:")
        print("-" * 100)
        
        updated_count, final_balance, issues = fix_null_balances_for_year(
            cur, account_number, year, apply_fixes=False
        )
        
        all_results[year] = (updated_count, final_balance, issues)
        total_updates += updated_count
        
        if updated_count > 0:
            print(f"  NULL balances to fill: {updated_count}")
            print(f"  Ending balance: ${final_balance:.2f}" if final_balance is not None else "  Ending balance: ERROR")
        else:
            print(f"  No NULL balances found (all already calculated)")
        
        if issues:
            print(f"  ⚠️ Issues: {issues[0]}")
    
    print("\n" + "="*100)
    print(f"SUMMARY: {total_updates} NULL balances ready to fill")
    print("="*100)
    
    if not apply_fixes:
        print("\nRun with --write flag to apply changes:")
        print(f"  python scripts/MASTER_fix_all_1615_balances.py --write")
    else:
        # Apply changes
        print("\nApplying changes to database...")
        
        for year in years:
            updated_count, final_balance, issues = fix_null_balances_for_year(
                cur, account_number, year, apply_fixes=True
            )
            if updated_count > 0:
                print(f"✅ {year}: Filled {updated_count} NULL balances, ending at ${final_balance:.2f}")
            else:
                print(f"⏭️ {year}: No updates needed")
        
        conn.commit()
        print("\n✅ All changes committed to database")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
