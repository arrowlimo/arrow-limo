"""
Recalculate and UPDATE all NULL balance fields in Scotia Bank account 903990106011.

This script:
1. Finds a known good opening balance
2. Calculates balances chronologically from that point
3. Updates all NULL balance fields with calculated values
4. Reports on changes made

Usage:
    python recalculate_scotia_null_balances.py          # Dry-run (shows what would be updated)
    python recalculate_scotia_null_balances.py --write  # Apply updates to database
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
        password=os.environ.get('DB_PASSWORD', '***REDACTED***')
    )


def find_opening_balance(cur):
    """
    Find the opening balance for Scotia account.
    
    Strategy: Find first transaction with a non-NULL balance field.
    If that's not reliable, work backwards from a known good balance.
    """
    # Try to find first non-NULL balance
    cur.execute("""
        SELECT transaction_id, transaction_date, balance, description
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND balance IS NOT NULL
        ORDER BY transaction_date, transaction_id
        LIMIT 1
    """)
    
    first_balance = cur.fetchone()
    
    if first_balance:
        txn_id, date, balance, desc = first_balance
        print(f"First known balance: ${balance:,.2f} on {date} (Txn {txn_id})")
        print(f"Description: {desc}")
        
        # Check if there are transactions before this one
        cur.execute("""
            SELECT COUNT(*) 
            FROM banking_transactions
            WHERE account_number = '903990106011'
            AND (transaction_date < %s OR (transaction_date = %s AND transaction_id < %s))
        """, (date, date, txn_id))
        
        count_before = cur.fetchone()[0]
        
        if count_before > 0:
            print(f"WARNING: {count_before} transactions exist before this balance")
            print("Will need to work backwards to calculate their balances")
            return None, None  # Need to handle this case
        else:
            return balance, (date, txn_id)
    
    return None, None


def recalculate_balances(cur, write=False):
    """
    Recalculate all NULL balances chronologically.
    
    Approach:
    1. Find opening balance from first non-NULL balance
    2. Calculate forward chronologically
    3. Update NULL balance fields
    """
    print("Fetching all Scotia transactions...")
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            balance
        FROM banking_transactions
        WHERE account_number = '903990106011'
        ORDER BY transaction_date, transaction_id
    """)
    
    transactions = cur.fetchall()
    print(f"Total transactions: {len(transactions)}")
    
    # Find opening balance
    opening_balance = None
    start_index = 0
    
    for i, txn in enumerate(transactions):
        if txn[5] is not None:  # balance field
            opening_balance = txn[5]
            start_index = i
            print(f"\nStarting from transaction {i+1} (ID {txn[0]})")
            print(f"Date: {txn[1]}, Opening balance: ${opening_balance:,.2f}")
            break
    
    if opening_balance is None:
        print("ERROR: No non-NULL balance found to start from!")
        print("Cannot proceed without a known good balance")
        return
    
    # Calculate backwards if needed (transactions before first known balance)
    if start_index > 0:
        print(f"\nCalculating backwards for {start_index} transactions before known balance...")
        running_balance = Decimal(str(opening_balance))
        
        updates_backward = []
        for i in range(start_index - 1, -1, -1):
            txn = transactions[i]
            txn_id = txn[0]
            debit = txn[3] or Decimal('0')
            credit = txn[4] or Decimal('0')
            recorded_balance = txn[5]
            
            # Work backwards: before this txn, balance was current - credit + debit
            running_balance = running_balance - Decimal(str(credit)) + Decimal(str(debit))
            
            if recorded_balance is None:
                updates_backward.append((txn_id, running_balance))
        
        # Reverse the list so we have them in chronological order
        updates_backward.reverse()
        
        print(f"Found {len(updates_backward)} NULL balances before known balance")
        
        if updates_backward and write:
            print("Updating backwards transactions...")
            for txn_id, calc_balance in updates_backward:
                cur.execute("""
                    UPDATE banking_transactions
                    SET balance = %s
                    WHERE transaction_id = %s
                """, (calc_balance, txn_id))
            print(f"Updated {len(updates_backward)} transactions")
    
    # Now calculate forward from opening balance
    print(f"\nCalculating forward from transaction {start_index + 1}...")
    running_balance = Decimal(str(opening_balance))
    
    updates_forward = []
    null_count = 0
    mismatch_count = 0
    
    for i in range(start_index, len(transactions)):
        txn = transactions[i]
        txn_id = txn[0]
        date = txn[1]
        desc = txn[2] or ''
        debit = txn[3] or Decimal('0')
        credit = txn[4] or Decimal('0')
        recorded_balance = txn[5]
        
        # Apply transaction to running balance
        running_balance = running_balance - Decimal(str(debit)) + Decimal(str(credit))
        
        if recorded_balance is None:
            null_count += 1
            updates_forward.append({
                'txn_id': txn_id,
                'date': date,
                'description': desc[:40],
                'calculated': running_balance,
                'was_null': True
            })
        else:
            # Check for mismatch
            diff = abs(running_balance - Decimal(str(recorded_balance)))
            if diff > Decimal('0.01'):
                mismatch_count += 1
                if mismatch_count <= 10:  # Show first 10 mismatches
                    print(f"  Mismatch at {date} (Txn {txn_id}): "
                          f"Calc ${running_balance:,.2f} vs Record ${recorded_balance:,.2f} "
                          f"(Diff ${diff:,.2f})")
            
            # Use recorded balance to prevent cascade errors
            running_balance = Decimal(str(recorded_balance))
    
    print(f"\nFound {null_count} NULL balances in forward calculation")
    print(f"Found {mismatch_count} balance mismatches (not updated, kept recorded values)")
    
    # Display sample of updates
    if updates_forward:
        print("\n" + "="*100)
        print("SAMPLE UPDATES (first 20 and last 20):")
        print("="*100)
        print(f"{'Date':<12} {'TxnID':<8} {'Description':<40} {'New Balance':>14}")
        print("-"*100)
        
        sample_updates = updates_forward[:20] + updates_forward[-20:] if len(updates_forward) > 40 else updates_forward
        
        for update in sample_updates:
            print(f"{update['date']} {update['txn_id']:<8} {update['description']:<40} ${update['calculated']:>12,.2f}")
        
        if len(updates_forward) > 40:
            print(f"... ({len(updates_forward) - 40} more updates) ...")
    
    # Apply updates if write mode
    if updates_forward and write:
        print(f"\n*** APPLYING {len(updates_forward)} UPDATES ***")
        
        for update in updates_forward:
            cur.execute("""
                UPDATE banking_transactions
                SET balance = %s
                WHERE transaction_id = %s
            """, (update['calculated'], update['txn_id']))
        
        print(f"Updated {len(updates_forward)} NULL balance fields")
    elif not write:
        print(f"\n*** DRY RUN MODE - Would update {len(updates_forward)} NULL balances ***")
        print("Run with --write to apply changes")
    
    return len(updates_forward)


def main():
    parser = argparse.ArgumentParser(description='Recalculate NULL balances for Scotia Bank')
    parser.add_argument('--write', action='store_true', 
                       help='Apply updates to database (default is dry-run)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Recalculate balances
        updated_count = recalculate_balances(cur, write=args.write)
        
        if args.write and updated_count > 0:
            conn.commit()
            print("\n" + "="*100)
            print("CHANGES COMMITTED TO DATABASE")
            print("="*100)
            print(f"Updated {updated_count} NULL balance fields")
            print("\nNext steps:")
            print("1. Re-run audit_scotia_running_balance.py to verify improvements")
            print("2. Check if duplicate transactions still cause oscillations")
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
