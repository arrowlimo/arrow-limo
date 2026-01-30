"""
Display Scotia Bank balance mismatches in detailed format for manual review.
Shows transactions with balance discrepancies for correction.
"""
import psycopg2
import os
from decimal import Decimal

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Fetch all Scotia transactions chronologically
    cur.execute("""
        SELECT transaction_id, transaction_date, description, 
               debit_amount, credit_amount, balance
        FROM banking_transactions
        WHERE account_number = '903990106011'
        ORDER BY transaction_date, transaction_id
    """)
    
    transactions = cur.fetchall()
    
    if not transactions:
        print("No transactions found for Scotia account 903990106011")
        return
    
    print(f"Total transactions: {len(transactions)}")
    print("="*120)
    
    # Find first transaction with a balance to use as opening
    opening_balance = Decimal('0')
    start_idx = 0
    for idx, txn in enumerate(transactions):
        if txn[5] is not None:  # balance field
            opening_balance = Decimal(str(txn[5]))
            # Work backwards to get opening before this transaction
            if txn[3]:  # debit
                opening_balance += Decimal(str(txn[3]))
            if txn[4]:  # credit
                opening_balance -= Decimal(str(txn[4]))
            start_idx = idx
            break
    
    print(f"Opening balance (calculated from first transaction with balance): ${opening_balance:,.2f}")
    print(f"Starting from transaction #{start_idx + 1}")
    print("="*120)
    print()
    
    running_balance = opening_balance
    mismatch_count = 0
    null_count = 0
    
    print("BALANCE MISMATCHES:")
    print("-"*120)
    print(f"{'Date':<12} {'TxnID':<8} {'Description':<40} {'Debit':<12} {'Credit':<12} {'Calc Bal':<14} {'Record Bal':<14} {'Diff':<12}")
    print("-"*120)
    
    for idx, txn in enumerate(transactions, 1):
        txn_id, txn_date, description, debit, credit, recorded_balance = txn
        
        # Apply transaction to running balance
        if debit:
            running_balance -= Decimal(str(debit))
        if credit:
            running_balance += Decimal(str(credit))
        
        # Check for mismatch or NULL
        if recorded_balance is None:
            null_count += 1
            # Only show first 100 NULLs to avoid spam
            if null_count <= 100:
                print(f"{txn_date} {txn_id:<8} {description[:40]:<40} "
                      f"${debit or 0:>10,.2f} ${credit or 0:>10,.2f} "
                      f"${running_balance:>12,.2f} {'NULL':<14} {'NULL':<12}")
        else:
            recorded_balance = Decimal(str(recorded_balance))
            difference = abs(running_balance - recorded_balance)
            
            if difference > Decimal('0.01'):
                mismatch_count += 1
                print(f"{txn_date} {txn_id:<8} {description[:40]:<40} "
                      f"${debit or 0:>10,.2f} ${credit or 0:>10,.2f} "
                      f"${running_balance:>12,.2f} ${recorded_balance:>12,.2f} ${difference:>10,.2f}")
            
            # Use recorded balance to prevent cascade errors
            running_balance = recorded_balance
    
    print("-"*120)
    print()
    print(f"SUMMARY:")
    print(f"  Total transactions: {len(transactions)}")
    print(f"  Balance mismatches: {mismatch_count}")
    print(f"  NULL balances: {null_count}")
    print(f"  Final calculated balance: ${running_balance:,.2f}")
    
    if null_count > 100:
        print(f"\nNote: Only first 100 NULL balances shown (total: {null_count})")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
