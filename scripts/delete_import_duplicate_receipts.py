#!/usr/bin/env python3
"""
Delete duplicate receipts created by import errors.

PROBLEM: Multiple receipts linked to the same banking transaction.
SOLUTION: Keep the receipt matching the banking debit amount, delete others.

This is the primary cause of the $6.3M over-inflation.
"""

import psycopg2
import os
from decimal import Decimal
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def main():
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("IMPORT DUPLICATE CLEANUP")
    print("Deleting receipts that duplicate banking transactions")
    print("=" * 80)
    print()
    
    # Find banking transactions with multiple receipts
    cur.execute("""
        SELECT 
            bt.transaction_id,
            bt.transaction_date,
            bt.description,
            bt.debit_amount,
            COUNT(r.receipt_id) as receipt_count,
            ARRAY_AGG(r.receipt_id ORDER BY r.receipt_id) as receipt_ids,
            ARRAY_AGG(r.gross_amount ORDER BY r.receipt_id) as receipt_amounts,
            ARRAY_AGG(r.receipt_source ORDER BY r.receipt_id) as sources
        FROM banking_transactions bt
        INNER JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
        WHERE r.exclude_from_reports = FALSE
        GROUP BY bt.transaction_id, bt.transaction_date, bt.description, bt.debit_amount
        HAVING COUNT(r.receipt_id) > 1
        ORDER BY bt.transaction_id
    """)
    
    multiple_receipt_txs = cur.fetchall()
    
    print(f"Found {len(multiple_receipt_txs)} banking transactions with multiple receipts\n")
    
    to_delete = []
    total_inflation_removed = Decimal('0')
    
    for tx_id, tx_date, tx_desc, tx_debit, rec_count, rec_ids, rec_amounts, sources in multiple_receipt_txs:
        
        banking_amt = Decimal(str(tx_debit)) if tx_debit else Decimal('0')
        
        # Find receipt(s) that match the banking amount
        matching_receipts = []
        non_matching_receipts = []
        
        for i, amt in enumerate(rec_amounts):
            receipt_amt = Decimal(str(amt)) if amt else Decimal('0')
            diff = abs(receipt_amt - banking_amt)
            
            if diff < Decimal('0.02'):  # Within 2 cents (rounding tolerance)
                matching_receipts.append((rec_ids[i], receipt_amt, sources[i]))
            else:
                non_matching_receipts.append((rec_ids[i], receipt_amt, sources[i]))
        
        # Decision logic
        if len(matching_receipts) == 1 and len(non_matching_receipts) > 0:
            # Clear case: 1 matching, rest are duplicates
            keep_id, keep_amt, keep_source = matching_receipts[0]
            
            for del_id, del_amt, del_source in non_matching_receipts:
                to_delete.append({
                    'receipt_id': del_id,
                    'amount': float(del_amt),
                    'banking_tx': tx_id,
                    'banking_amt': float(banking_amt),
                    'reason': f'Duplicate (keep #{keep_id} ${keep_amt})'
                })
                total_inflation_removed += del_amt
                
                print(f"TX #{tx_id}: DELETE receipt #{del_id} (${del_amt}), KEEP #{keep_id} (${keep_amt} = banking)")
        
        elif len(matching_receipts) == 0:
            # No exact match - keep the first one (arbitrary but consistent)
            keep_id = rec_ids[0]
            keep_amt = Decimal(str(rec_amounts[0])) if rec_amounts[0] else Decimal('0')
            
            for i in range(1, len(rec_ids)):
                del_id = rec_ids[i]
                del_amt = Decimal(str(rec_amounts[i])) if rec_amounts[i] else Decimal('0')
                
                to_delete.append({
                    'receipt_id': del_id,
                    'amount': float(del_amt),
                    'banking_tx': tx_id,
                    'banking_amt': float(banking_amt),
                    'reason': f'Duplicate (keep first #{keep_id})'
                })
                total_inflation_removed += del_amt
                
                print(f"TX #{tx_id}: DELETE receipt #{del_id} (${del_amt}), KEEP #{keep_id} (${keep_amt}) - no exact match")
        
        elif len(matching_receipts) > 1:
            # Multiple matching - keep the first, delete rest
            keep_id, keep_amt, keep_source = matching_receipts[0]
            
            for del_id, del_amt, del_source in matching_receipts[1:] + non_matching_receipts:
                to_delete.append({
                    'receipt_id': del_id,
                    'amount': float(del_amt),
                    'banking_tx': tx_id,
                    'banking_amt': float(banking_amt),
                    'reason': f'Duplicate (keep first match #{keep_id})'
                })
                total_inflation_removed += del_amt
                
                print(f"TX #{tx_id}: DELETE receipt #{del_id} (${del_amt}), KEEP #{keep_id} (${keep_amt})")
    
    # Summary
    print("\n" + "=" * 80)
    print("DELETION SUMMARY")
    print("=" * 80)
    
    print(f"\nReceipts to delete: {len(to_delete)}")
    print(f"Total inflation removed: ${total_inflation_removed:,.2f}")
    
    if to_delete:
        print(f"\nTop 20 deletions by amount:")
        for d in sorted(to_delete, key=lambda x: x['amount'], reverse=True)[:20]:
            print(f"  Receipt #{d['receipt_id']}: ${d['amount']:,.2f} (TX #{d['banking_tx']}, banking=${d['banking_amt']:,.2f})")
    
    # Confirm deletion
    print("\n" + "=" * 80)
    print(f"\nPROCEEDING WITH DELETION: {len(to_delete)} receipts (${total_inflation_removed:,.2f})")
    print("=" * 80)
    
    # First, NULL out any banking_transactions.receipt_id references
    print("\nClearing banking_transactions.receipt_id references...")
    receipt_ids_to_delete = [d['receipt_id'] for d in to_delete]
    
    cur.execute("""
        UPDATE banking_transactions 
        SET receipt_id = NULL 
        WHERE receipt_id = ANY(%s)
    """, (receipt_ids_to_delete,))
    
    print(f"  Cleared {cur.rowcount} banking_transactions.receipt_id references")
    
    # Delete receipts
    print("\nDeleting receipts...")
    
    deleted_count = 0
    for d in to_delete:
        cur.execute("""
            DELETE FROM receipts WHERE receipt_id = %s
        """, (d['receipt_id'],))
        deleted_count += 1
        
        if deleted_count % 50 == 0:
            print(f"  Deleted {deleted_count}/{len(to_delete)} receipts...")
    
    conn.commit()
    
    print(f"\n✅ Successfully deleted {deleted_count} duplicate receipts")
    print(f"✅ Removed ${total_inflation_removed:,.2f} inflation")
    
    # Verify
    cur.execute("""
        SELECT COUNT(*) 
        FROM banking_transactions bt
        INNER JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
        WHERE r.exclude_from_reports = FALSE
        GROUP BY bt.transaction_id
        HAVING COUNT(r.receipt_id) > 1
    """)
    
    remaining_dupes = cur.rowcount
    print(f"\nRemaining banking TXs with multiple receipts: {remaining_dupes}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
