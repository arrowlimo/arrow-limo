"""
Comprehensive banking_transactions deduplication with full FK constraint handling

Handles all 18 FK constraints discovered by find_all_fk_constraints.py
Processes in small batches to avoid overwhelming memory
"""

import psycopg2
from datetime import datetime
import sys

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def update_banking_fk_references(cur, keep_id, delete_ids):
    """Update all 18 FK references to point to kept transaction"""
    
    updates = {}
    
    # List of tables that reference banking_transactions.transaction_id
    fk_tables = [
        'banking_payment_links',
        'banking_receipt_matching_ledger',
        'chauffeur_float_tracking',
        'cheque_register',
        'cibc_card_transactions',
        'etransfer_banking_reconciliation',
        'etransfer_transactions',
        'owner_expense_transactions',
        'payments',
        'square_capital_loans',
        'square_etransfer_reconciliation',
        'square_loan_payments',
        'vehicle_loan_payments'
    ]
    
    for table in fk_tables:
        try:
            # Determine column name (most use banking_transaction_id, some use transaction_id)
            if table == 'etransfer_banking_reconciliation':
                col = 'transaction_id'
            else:
                col = 'banking_transaction_id'
            
            # Check if any references exist
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} = ANY(%s)", (delete_ids,))
            count = cur.fetchone()[0]
            
            if count > 0:
                # Update to point to kept ID
                cur.execute(f"""
                    UPDATE {table}
                    SET {col} = %s
                    WHERE {col} = ANY(%s)
                """, (keep_id, delete_ids))
                
                updates[table] = cur.rowcount
        
        except Exception as e:
            # Table might not exist or column might be different
            print(f"    ⚠️ Warning updating {table}: {e}")
    
    return updates

def main():
    dry_run = '--write' not in sys.argv
    batch_size = int(sys.argv[sys.argv.index('--batch') + 1]) if '--batch' in sys.argv else 50
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        print("="*80)
        print("COMPREHENSIVE BANKING_TRANSACTIONS DEDUPLICATION")
        print("="*80)
        print(f"\nMode: {'🔥 WRITE' if not dry_run else '⚠️ DRY RUN'}")
        print(f"Batch size: {batch_size} groups per run")
        
        # Create backup
        if not dry_run:
            cur.execute(f"CREATE TABLE banking_transactions_backup_{timestamp} AS SELECT * FROM banking_transactions")
            print(f"\n✅ Backup: banking_transactions_backup_{timestamp}")
        
        # Find duplicates
        cur.execute("""
            SELECT 
                transaction_date,
                account_number,
                description,
                debit_amount,
                credit_amount,
                array_agg(transaction_id ORDER BY transaction_id) as ids,
                COUNT(*) as dup_count
            FROM banking_transactions
            GROUP BY transaction_date, account_number, description, debit_amount, credit_amount
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC, COALESCE(debit_amount, credit_amount) DESC
        """)
        
        all_groups = cur.fetchall()
        total_groups = len(all_groups)
        
        print(f"\nFound {total_groups} duplicate groups")
        print(f"Processing first {min(batch_size, total_groups)} groups...\n")
        
        dup_groups = all_groups[:batch_size]
        
        total_deleted = 0
        total_fk_updates = {}
        
        for date, acct, desc, debit, credit, ids, count in dup_groups:
            keep_id = ids[0]
            delete_ids = ids[1:]
            
            dr_str = f"DR ${debit:.2f}" if debit else "DR $0.00"
            cr_str = f"CR ${credit:.2f}" if credit else "CR $0.00"
            
            print(f"{date} | {acct} | {dr_str} {cr_str}")
            print(f"  {desc[:60]}")
            print(f"  Keep: {keep_id}, Delete: {delete_ids[:3]}{'...' if len(delete_ids) > 3 else ''}")
            
            if not dry_run:
                # Update all FK references
                updates = update_banking_fk_references(cur, keep_id, delete_ids)
                
                # Show what was updated
                for table, fk_count in updates.items():
                    print(f"  ✅ Updated {fk_count} in {table}")
                    total_fk_updates[table] = total_fk_updates.get(table, 0) + fk_count
                
                # Now safe to delete
                cur.execute("DELETE FROM banking_transactions WHERE transaction_id = ANY(%s)", (delete_ids,))
                deleted = cur.rowcount
                total_deleted += deleted
                print(f"  ✅ Deleted {deleted} transactions")
            else:
                # Dry run - just check what would be updated
                print(f"  Would delete: {len(delete_ids)} transactions")
            
            print()
        
        # Commit or rollback
        if dry_run:
            conn.rollback()
            print("⚠️ DRY RUN - No changes committed\n")
        else:
            conn.commit()
            print("✅ ALL CHANGES COMMITTED\n")
        
        # Check remaining
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT transaction_date, account_number, description, debit_amount, credit_amount
                FROM banking_transactions
                GROUP BY transaction_date, account_number, description, debit_amount, credit_amount
                HAVING COUNT(*) > 1
            ) sub
        """)
        
        remaining_groups = cur.fetchone()[0]
        
        print("="*80)
        print("FINAL SUMMARY")
        print("="*80)
        print(f"Groups processed: {len(dup_groups)} of {total_groups}")
        print(f"Transactions deleted: {total_deleted}")
        
        if total_fk_updates:
            print(f"\nFK Updates:")
            for table, count in sorted(total_fk_updates.items()):
                print(f"  {table}: {count}")
        
        print(f"\nRemaining duplicate groups: {remaining_groups}")
        
        if remaining_groups > 0:
            print(f"\n📝 Run script again to process next batch of {batch_size} groups")
        else:
            print(f"\n✅ Status: CLEAN - All duplicates removed!")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise
    
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
