"""
Find duplicate transactions in CIBC account 0228362.

Identifies transactions with same date, amount, and similar descriptions
that may be causing the balance discrepancies.

Usage:
    python find_cibc_duplicate_transactions.py          # Dry-run
    python find_cibc_duplicate_transactions.py --write  # Mark duplicates for review
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal
from collections import defaultdict
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


def normalize_description(desc):
    """Normalize description for comparison."""
    if not desc:
        return ""
    return ' '.join(desc.upper().split())


def find_duplicates(cur):
    """Find potential duplicate transactions in CIBC account."""
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
    
    # Group by date + amount
    groups = defaultdict(list)
    
    for txn in transactions:
        date = txn['transaction_date']
        debit = txn['debit_amount'] or Decimal('0')
        credit = txn['credit_amount'] or Decimal('0')
        
        if debit > 0:
            key = (date, 'D', debit)
            groups[key].append(txn)
        if credit > 0:
            key = (date, 'C', credit)
            groups[key].append(txn)
    
    # Find groups with multiple transactions
    duplicates = []
    for key, txns in groups.items():
        if len(txns) > 1:
            date, txn_type, amount = key
            
            # Normalize descriptions
            normalized = [(txn, normalize_description(txn['description'])) for txn in txns]
            
            # Group by normalized description
            desc_groups = defaultdict(list)
            for txn, norm_desc in normalized:
                desc_groups[norm_desc].append(txn)
            
            # Report groups with same normalized description
            for norm_desc, same_desc_txns in desc_groups.items():
                if len(same_desc_txns) > 1:
                    duplicates.append({
                        'date': date,
                        'type': 'DEBIT' if txn_type == 'D' else 'CREDIT',
                        'amount': amount,
                        'description': norm_desc,
                        'count': len(same_desc_txns),
                        'transactions': same_desc_txns
                    })
    
    return duplicates


def display_duplicates(duplicates):
    """Display duplicate transaction groups."""
    print("\n" + "="*120)
    print("DUPLICATE TRANSACTION GROUPS - CIBC 0228362")
    print("="*120)
    
    if not duplicates:
        print("No duplicates found!")
        return
    
    total_duplicate_count = 0
    total_affected_amount = Decimal('0')
    
    for i, dup_group in enumerate(duplicates, 1):
        date = dup_group['date']
        txn_type = dup_group['type']
        amount = dup_group['amount']
        desc = dup_group['description']
        count = dup_group['count']
        txns = dup_group['transactions']
        
        print(f"\n--- Group {i}: {count} transactions on {date} ---")
        print(f"Type: {txn_type} | Amount: ${amount:,.2f} | Description: {desc[:60]}")
        print(f"{'TxnID':<10} {'Debit':>12} {'Credit':>12} {'Balance':>14} {'Description':<50}")
        print("-" * 100)
        
        for txn in txns:
            txn_id = txn['transaction_id']
            debit = txn['debit_amount'] or Decimal('0')
            credit = txn['credit_amount'] or Decimal('0')
            balance = txn['balance'] if txn['balance'] is not None else 'NULL'
            desc_full = txn['description'] or ''
            
            if isinstance(balance, Decimal):
                balance_str = f"${balance:>12,.2f}"
            else:
                balance_str = f"{'NULL':>14}"
            
            print(f"{txn_id:<10} ${debit:>10,.2f} ${credit:>10,.2f} {balance_str} {desc_full[:50]}")
        
        duplicate_count = count - 1
        total_duplicate_count += duplicate_count
        total_affected_amount += amount * duplicate_count
    
    print("\n" + "="*120)
    print(f"SUMMARY: {len(duplicates)} duplicate groups found")
    print(f"Total duplicate transactions: {total_duplicate_count}")
    print(f"Total affected amount: ${total_affected_amount:,.2f}")
    print("="*120)
    
    return duplicates


def mark_duplicates_for_review(cur, duplicates, write=False):
    """Mark duplicate transactions for manual review."""
    if not write:
        print("\n*** DRY RUN MODE - No changes will be made ***")
        print("Run with --write to mark duplicates for review")
        return
    
    print("\nMarking duplicates for review...")
    
    marked_count = 0
    for dup_group in duplicates:
        txns = dup_group['transactions']
        txns_sorted = sorted(txns, key=lambda x: x['transaction_id'])
        
        for txn in txns_sorted[1:]:
            txn_id = txn['transaction_id']
            original_desc = txn['description'] or ''
            new_desc = f"[DUPLICATE?] {original_desc}"
            
            cur.execute("""
                UPDATE banking_transactions
                SET description = %s
                WHERE transaction_id = %s
            """, (new_desc, txn_id))
            
            marked_count += 1
            print(f"  Marked transaction {txn_id} as potential duplicate")
    
    print(f"\nMarked {marked_count} transactions for review")


def main():
    parser = argparse.ArgumentParser(description='Find duplicate CIBC transactions')
    parser.add_argument('--write', action='store_true', 
                       help='Mark duplicates for review (default is dry-run)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        duplicates = find_duplicates(cur)
        display_duplicates(duplicates)
        
        if duplicates:
            mark_duplicates_for_review(cur, duplicates, write=args.write)
            
            if args.write:
                conn.commit()
                print("\nChanges committed to database")
            else:
                print("\nNo changes made (dry-run mode)")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    main()
