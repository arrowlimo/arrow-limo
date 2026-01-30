"""
Comprehensive payments deduplication with full FK constraint handling

Handles all 6 FK constraints:
1. banking_payment_links.payment_id
2. income_ledger.payment_id
3. multi_charter_payments.payment_id
4. payment_reconciliation_ledger.payment_id
5. payments.related_payment_id (self-referencing)
6. square_etransfer_reconciliation.square_payment_id
"""

import psycopg2
from datetime import datetime
import sys

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def update_fk_references(cur, keep_id, delete_ids):
    """Update all FK references to point to kept payment"""
    
    updates = {
        'banking_payment_links': 0,
        'income_ledger': 0,
        'multi_charter_payments': 0,
        'payment_reconciliation_ledger': 0,
        'payments_self_ref': 0,
        'square_etransfer_reconciliation': 0
    }
    
    # 1. banking_payment_links
    cur.execute("""
        SELECT COUNT(*) FROM banking_payment_links 
        WHERE payment_id = ANY(%s)
    """, (delete_ids,))
    if cur.fetchone()[0] > 0:
        cur.execute("""
            UPDATE banking_payment_links
            SET payment_id = %s
            WHERE payment_id = ANY(%s)
        """, (keep_id, delete_ids))
        updates['banking_payment_links'] = cur.rowcount
    
    # 2. income_ledger
    cur.execute("""
        SELECT COUNT(*) FROM income_ledger 
        WHERE payment_id = ANY(%s)
    """, (delete_ids,))
    if cur.fetchone()[0] > 0:
        cur.execute("""
            UPDATE income_ledger
            SET payment_id = %s
            WHERE payment_id = ANY(%s)
        """, (keep_id, delete_ids))
        updates['income_ledger'] = cur.rowcount
    
    # 3. multi_charter_payments
    cur.execute("""
        SELECT COUNT(*) FROM multi_charter_payments 
        WHERE payment_id = ANY(%s)
    """, (delete_ids,))
    if cur.fetchone()[0] > 0:
        cur.execute("""
            UPDATE multi_charter_payments
            SET payment_id = %s
            WHERE payment_id = ANY(%s)
        """, (keep_id, delete_ids))
        updates['multi_charter_payments'] = cur.rowcount
    
    # 4. payment_reconciliation_ledger
    cur.execute("""
        SELECT COUNT(*) FROM payment_reconciliation_ledger 
        WHERE payment_id = ANY(%s)
    """, (delete_ids,))
    if cur.fetchone()[0] > 0:
        cur.execute("""
            UPDATE payment_reconciliation_ledger
            SET payment_id = %s
            WHERE payment_id = ANY(%s)
        """, (keep_id, delete_ids))
        updates['payment_reconciliation_ledger'] = cur.rowcount
    
    # 5. payments.related_payment_id (self-referencing)
    cur.execute("""
        SELECT COUNT(*) FROM payments 
        WHERE related_payment_id = ANY(%s)
    """, (delete_ids,))
    if cur.fetchone()[0] > 0:
        cur.execute("""
            UPDATE payments
            SET related_payment_id = %s
            WHERE related_payment_id = ANY(%s)
        """, (keep_id, delete_ids))
        updates['payments_self_ref'] = cur.rowcount
    
    # 6. square_etransfer_reconciliation
    cur.execute("""
        SELECT COUNT(*) FROM square_etransfer_reconciliation 
        WHERE square_payment_id = ANY(%s)
    """, (delete_ids,))
    if cur.fetchone()[0] > 0:
        cur.execute("""
            UPDATE square_etransfer_reconciliation
            SET square_payment_id = %s
            WHERE square_payment_id = ANY(%s)
        """, (keep_id, delete_ids))
        updates['square_etransfer_reconciliation'] = cur.rowcount
    
    return updates

def main():
    dry_run = '--write' not in sys.argv
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        print("="*80)
        print("COMPREHENSIVE PAYMENTS DEDUPLICATION")
        print("="*80)
        print(f"\nMode: {'🔥 WRITE' if not dry_run else '⚠️ DRY RUN'}")
        
        # Create backup
        if not dry_run:
            cur.execute(f"CREATE TABLE payments_backup_{timestamp} AS SELECT * FROM payments")
            print(f"\n✅ Backup: payments_backup_{timestamp}")
        
        # Find duplicates
        cur.execute("""
            SELECT 
                reserve_number,
                amount,
                payment_date,
                array_agg(payment_id ORDER BY payment_id) as ids,
                COUNT(*) as dup_count
            FROM payments
            GROUP BY reserve_number, amount, payment_date
            HAVING COUNT(*) > 1
        """)
        
        dup_groups = cur.fetchall()
        print(f"\nFound {len(dup_groups)} duplicate groups\n")
        
        total_deleted = 0
        total_updates = {
            'banking_payment_links': 0,
            'income_ledger': 0,
            'multi_charter_payments': 0,
            'payment_reconciliation_ledger': 0,
            'payments_self_ref': 0,
            'square_etransfer_reconciliation': 0
        }
        
        for rsv, amt, date, ids, count in dup_groups:
            keep_id = ids[0]
            delete_ids = ids[1:]
            
            print(f"Reserve {rsv or 'None'} | {date} | ${amt:.2f}")
            print(f"  Keep: {keep_id}, Delete: {delete_ids}")
            
            if not dry_run:
                # Update all FK references
                updates = update_fk_references(cur, keep_id, delete_ids)
                
                # Show what was updated
                for table, count in updates.items():
                    if count > 0:
                        print(f"  ✅ Updated {count} in {table}")
                        total_updates[table] += count
                
                # Now safe to delete
                cur.execute("DELETE FROM payments WHERE payment_id = ANY(%s)", (delete_ids,))
                deleted = cur.rowcount
                total_deleted += deleted
                print(f"  ✅ Deleted {deleted} payments")
            else:
                # Dry run - just check FK references
                updates = {}
                
                # Tables with payment_id column
                for table in ['banking_payment_links', 'income_ledger', 'multi_charter_payments', 
                             'payment_reconciliation_ledger']:
                    cur.execute(f"SELECT COUNT(*) FROM {table} WHERE payment_id = ANY(%s)", (delete_ids,))
                    count = cur.fetchone()[0]
                    if count > 0:
                        updates[table] = count
                
                # square_etransfer_reconciliation uses square_payment_id
                cur.execute("SELECT COUNT(*) FROM square_etransfer_reconciliation WHERE square_payment_id = ANY(%s)", (delete_ids,))
                count = cur.fetchone()[0]
                if count > 0:
                    updates['square_etransfer_reconciliation'] = count
                
                # Self-referencing
                cur.execute("SELECT COUNT(*) FROM payments WHERE related_payment_id = ANY(%s)", (delete_ids,))
                count = cur.fetchone()[0]
                if count > 0:
                    updates['payments_self_ref'] = count
                
                if updates:
                    print(f"  Would update: {updates}")
            
            print()
        
        # Commit or rollback
        if dry_run:
            conn.rollback()
            print("⚠️ DRY RUN - No changes committed\n")
        else:
            conn.commit()
            print("✅ ALL CHANGES COMMITTED\n")
        
        # Verify
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT reserve_number, amount, payment_date
                FROM payments
                GROUP BY reserve_number, amount, payment_date
                HAVING COUNT(*) > 1
            ) sub
        """)
        
        remaining = cur.fetchone()[0]
        
        print("="*80)
        print("FINAL SUMMARY")
        print("="*80)
        print(f"Payments deleted: {total_deleted}")
        print(f"\nFK Updates:")
        for table, count in total_updates.items():
            if count > 0:
                print(f"  {table}: {count}")
        print(f"\nRemaining duplicates: {remaining}")
        print(f"Status: {'✅ CLEAN' if remaining == 0 else '⚠️ DUPLICATES REMAIN'}")
        
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
