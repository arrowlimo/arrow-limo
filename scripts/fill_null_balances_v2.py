"""
Fill NULL balances only, without recalculating existing ones.
This is the corrected approach.
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

def fill_nulls_for_year(cur, account_number, year, apply_fixes=False):
    """Fill NULL balances by calculating forward from last known balance."""
    
    # Get all transactions in order
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
        return 0, None
    
    # Find first transaction with a non-NULL balance
    running_balance = None
    start_idx = 0
    
    for i, txn in enumerate(transactions):
        if txn[5] is not None:
            running_balance = Decimal(str(txn[5]))
            start_idx = i + 1
            break
    
    # If no non-NULL balance in this year, need to get from previous year
    if running_balance is None:
        prev_year = year - 1
        cur.execute("""
            SELECT balance FROM banking_transactions
            WHERE account_number = %s
            AND EXTRACT(YEAR FROM transaction_date) = %s
            ORDER BY transaction_date DESC, transaction_id DESC
            LIMIT 1
        """, (account_number, prev_year))
        
        result = cur.fetchone()
        if result and result[0] is not None:
            running_balance = Decimal(str(result[0]))
        else:
            return 0, None  # Can't calculate without starting balance
        
        start_idx = 0  # Start from beginning of year
    
    # Calculate forward and collect updates
    updates = []
    for txn in transactions[start_idx:]:
        txn_id, date, desc, debit, credit, old_balance = txn
        
        # Only process if NULL
        if old_balance is None:
            # Calculate new balance
            if debit:
                running_balance -= Decimal(str(debit))
            if credit:
                running_balance += Decimal(str(credit))
            
            updates.append((running_balance, txn_id))
        else:
            # Skip forward with the non-NULL balance
            running_balance = Decimal(str(old_balance))
    
    # Apply updates
    if apply_fixes and updates:
        for balance, txn_id in updates:
            cur.execute("""
                UPDATE banking_transactions 
                SET balance = %s 
                WHERE transaction_id = %s
            """, (balance, txn_id))
    
    return len(updates), running_balance

def main():
    apply_fixes = '--write' in sys.argv
    account_number = '1615'
    years = [2013, 2014, 2015, 2016, 2017]  # 2012 already complete
    
    print("="*100)
    print("CIBC 1615 - Fill NULL Balances Only")
    print("="*100)
    print(f"Mode: {'APPLYING FIXES' if apply_fixes else 'DRY-RUN'}")
    print()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    total_updates = 0
    results = {}
    
    for year in years:
        print(f"\n{year}:")
        print("-" * 100)
        
        updates, final_bal = fill_nulls_for_year(cur, account_number, year, apply_fixes=apply_fixes)
        total_updates += updates
        results[year] = (updates, final_bal)
        
        print(f"  NULL balances to fill: {updates}")
        if final_bal is not None:
            print(f"  Year ending balance: ${final_bal:.2f}")
    
    print("\n" + "="*100)
    print(f"TOTAL UPDATES: {total_updates} NULL balance fields")
    print("="*100)
    
    if apply_fixes:
        conn.commit()
        print("\n✅ All updates committed to database")
        
        # Verify
        print("\nVerification:")
        for year in years:
            cur.execute("""
                SELECT COUNT(*),
                       COUNT(CASE WHEN balance IS NULL THEN 1 END)
                FROM banking_transactions
                WHERE account_number = %s
                AND EXTRACT(YEAR FROM transaction_date) = %s
            """, (account_number, year))
            total, nulls = cur.fetchone()
            print(f"  {year}: {total} txns, {nulls} still NULL")
    else:
        print(f"\nRun with --write to apply {total_updates} updates:")
        print(f"  python scripts/fill_null_balances_v2.py --write")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
