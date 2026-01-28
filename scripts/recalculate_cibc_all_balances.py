"""
Recalculate ALL balance fields in CIBC account 0228362 from scratch.

Uses known opening balance from PDF statement and recalculates chronologically.

Usage:
    python recalculate_cibc_all_balances.py          # Dry-run
    python recalculate_cibc_all_balances.py --write  # Apply updates
"""

import psycopg2
from decimal import Decimal
import os
import argparse


def get_db_connection():
    """Get database connection using environment variables."""
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REMOVED***')
    )


def recalculate_all_balances(cur, write=False):
    """
    Recalculate ALL balances chronologically.
    
    Starting point: Jan 1, 2012 opening balance = $7,177.34 (from PDF)
    """
    print("Fetching all CIBC transactions...")
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            balance
        FROM banking_transactions
        WHERE account_number = '0228362'
        ORDER BY transaction_date, transaction_id
    """)
    
    transactions = cur.fetchall()
    print(f"Total transactions: {len(transactions)}")
    
    if not transactions:
        print("No transactions found!")
        return
    
    # Known opening balance from PDF statement
    OPENING_BALANCE = Decimal('7177.34')
    
    first_txn_date = transactions[0][1]
    print(f"\nFirst transaction date: {first_txn_date}")
    print(f"Starting with opening balance: ${OPENING_BALANCE:,.2f}")
    
    # Check if first transaction is January 1, 2012
    if first_txn_date.strftime('%Y-%m-%d') == '2012-01-01':
        print("First transaction is Jan 1, 2012 - using opening balance directly")
        running_balance = OPENING_BALANCE
    else:
        print(f"WARNING: First transaction is {first_txn_date}, not Jan 1, 2012")
        print("Using opening balance anyway...")
        running_balance = OPENING_BALANCE
    
    updates = []
    mismatch_count = 0
    
    for i, txn in enumerate(transactions):
        txn_id = txn[0]
        date = txn[1]
        desc = txn[2] or ''
        debit = txn[3] or Decimal('0')
        credit = txn[4] or Decimal('0')
        recorded_balance = txn[5]
        
        # Apply transaction
        running_balance = running_balance - Decimal(str(debit)) + Decimal(str(credit))
        
        # Check if different from recorded
        if recorded_balance is not None:
            diff = abs(running_balance - Decimal(str(recorded_balance)))
            if diff > Decimal('0.01'):
                mismatch_count += 1
        
        updates.append({
            'txn_id': txn_id,
            'date': date,
            'description': desc[:40],
            'debit': debit,
            'credit': credit,
            'old_balance': recorded_balance,
            'new_balance': running_balance,
            'changed': recorded_balance is None or abs(running_balance - Decimal(str(recorded_balance))) > Decimal('0.01')
        })
    
    # Count changes
    changed_count = sum(1 for u in updates if u['changed'])
    
    print(f"\nFound {changed_count} balances that will be updated")
    print(f"Found {mismatch_count} mismatches from recorded balances")
    
    # Display sample
    print("\n" + "="*120)
    print("SAMPLE UPDATES (first 10 and last 10):")
    print("="*120)
    print(f"{'Date':<12} {'TxnID':<8} {'Description':<30} {'Old Balance':>14} {'New Balance':>14} {'Status':<10}")
    print("-"*120)
    
    sample_updates = updates[:10] + updates[-10:] if len(updates) > 20 else updates
    
    for update in sample_updates:
        old_bal_str = f"${update['old_balance']:>12,.2f}" if update['old_balance'] else "NULL"
        new_bal_str = f"${update['new_balance']:>12,.2f}"
        status = "CHANGED" if update['changed'] else "SAME"
        
        print(f"{update['date']} {update['txn_id']:<8} {update['description']:<30} "
              f"{old_bal_str:>14} {new_bal_str:>14} {status:<10}")
    
    if len(updates) > 20:
        print(f"... ({len(updates) - 20} more updates) ...")
    
    # Apply updates if write mode
    if write:
        print(f"\n*** APPLYING {len(updates)} BALANCE UPDATES ***")
        
        for update in updates:
            cur.execute("""
                UPDATE banking_transactions
                SET balance = %s
                WHERE transaction_id = %s
            """, (update['new_balance'], update['txn_id']))
        
        print(f"Updated {len(updates)} balance fields")
        print(f"Changed {changed_count} balances from recorded values")
    else:
        print(f"\n*** DRY RUN MODE - Would update {len(updates)} balances ***")
        print(f"Would change {changed_count} balances from recorded values")
        print("Run with --write to apply changes")
    
    return len(updates), changed_count


def main():
    parser = argparse.ArgumentParser(description='Recalculate ALL CIBC balances')
    parser.add_argument('--write', action='store_true', 
                       help='Apply updates to database (default is dry-run)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        total_count, changed_count = recalculate_all_balances(cur, write=args.write)
        
        if args.write and total_count > 0:
            conn.commit()
            print("\n" + "="*120)
            print("CHANGES COMMITTED TO DATABASE")
            print("="*120)
            print(f"Updated {total_count} balance fields")
            print(f"Changed {changed_count} from recorded values")
            print("\nNext steps:")
            print("1. Re-run verify_cibc_monthly_totals_2012.py to check monthly totals")
            print("2. Verify balances match PDF statements")
        else:
            print("\nNo changes made (dry-run mode)")
        
    except Exception as e:
        print(f"\nError: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    main()
