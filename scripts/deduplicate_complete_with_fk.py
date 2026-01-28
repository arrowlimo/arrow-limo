"""
Complete deduplication handling ALL foreign key constraints

This script fixes the FK constraint issues discovered during cleanup:
- banking_payment_links.payment_id -> payments.payment_id
- banking_payment_links.banking_transaction_id -> banking_transactions.transaction_id

Strategy: Update all FK references to point to the kept record before deleting duplicates
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

def deduplicate_with_fk_handling(dry_run=True):
    """
    Handle all remaining duplicates with proper FK management
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        print("="*80)
        print("COMPREHENSIVE DEDUPLICATION WITH FK HANDLING")
        print("="*80)
        
        if dry_run:
            print("\n⚠️ DRY RUN MODE")
        else:
            print("\n🔥 WRITE MODE - Changes will be committed")
        
        # ====================================================================
        # 1. PAYMENTS - Handle banking_payment_links FK
        # ====================================================================
        print("\n" + "="*80)
        print("1. PAYMENTS TABLE")
        print("="*80)
        
        if not dry_run:
            cur.execute(f"CREATE TABLE payments_backup_{timestamp} AS SELECT * FROM payments")
            print(f"✅ Backup: payments_backup_{timestamp}")
        
        # Find payment duplicates
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
        
        payment_groups = cur.fetchall()
        print(f"\nFound {len(payment_groups)} payment duplicate groups")
        
        total_payment_deleted = 0
        total_payment_links_updated = 0
        
        for rsv, amt, date, ids, count in payment_groups:
            keep_id = ids[0]
            delete_ids = ids[1:]
            
            print(f"\n  Reserve {rsv} | {date} | ${amt:.2f}")
            print(f"    Keep: {keep_id}, Delete: {delete_ids}")
            
            # Check for banking_payment_links
            cur.execute("""
                SELECT COUNT(*) 
                FROM banking_payment_links 
                WHERE payment_id = ANY(%s)
            """, (delete_ids,))
            
            link_count = cur.fetchone()[0]
            
            if link_count > 0:
                print(f"    Found {link_count} banking_payment_links to update")
                
                if not dry_run:
                    # Update links to point to kept payment
                    cur.execute("""
                        UPDATE banking_payment_links
                        SET payment_id = %s
                        WHERE payment_id = ANY(%s)
                    """, (keep_id, delete_ids))
                    
                    updated = cur.rowcount
                    total_payment_links_updated += updated
                    print(f"    ✅ Updated {updated} links")
            
            # Delete duplicates
            if not dry_run:
                cur.execute("DELETE FROM payments WHERE payment_id = ANY(%s)", (delete_ids,))
                deleted = cur.rowcount
                total_payment_deleted += deleted
                print(f"    ✅ Deleted {deleted} duplicate payments")
        
        print(f"\n📊 Payments Summary:")
        print(f"   Deleted: {total_payment_deleted}")
        print(f"   Links updated: {total_payment_links_updated}")
        
        # ====================================================================
        # 2. CHARTER_CHARGES - No FK constraints expected
        # ====================================================================
        print("\n" + "="*80)
        print("2. CHARTER_CHARGES TABLE")
        print("="*80)
        
        if not dry_run:
            cur.execute(f"CREATE TABLE charter_charges_backup_{timestamp} AS SELECT * FROM charter_charges")
            print(f"✅ Backup: charter_charges_backup_{timestamp}")
        
        cur.execute("""
            SELECT 
                charter_id,
                description,
                amount,
                array_agg(charge_id ORDER BY charge_id) as ids
            FROM charter_charges
            GROUP BY charter_id, description, amount
            HAVING COUNT(*) > 1
        """)
        
        charge_groups = cur.fetchall()
        print(f"\nFound {len(charge_groups)} charter_charges duplicate groups")
        
        total_charges_deleted = 0
        
        for charter_id, desc, amt, ids in charge_groups:
            keep_id = ids[0]
            delete_ids = ids[1:]
            
            if not dry_run:
                cur.execute("DELETE FROM charter_charges WHERE charge_id = ANY(%s)", (delete_ids,))
                deleted = cur.rowcount
                total_charges_deleted += deleted
        
        print(f"📊 Charter Charges: Deleted {total_charges_deleted}")
        
        # ====================================================================
        # 3. JOURNAL - Single specific duplicate
        # ====================================================================
        print("\n" + "="*80)
        print("3. JOURNAL TABLE")
        print("="*80)
        
        if not dry_run:
            cur.execute(f"CREATE TABLE journal_backup_{timestamp} AS SELECT * FROM journal")
            print(f"✅ Backup: journal_backup_{timestamp}")
            
            cur.execute("DELETE FROM journal WHERE journal_id = 936")
            print(f"📊 Journal: Deleted {cur.rowcount}")
        else:
            print("Would delete journal_id 936")
        
        # ====================================================================
        # 4. RENT_DEBT_LEDGER - No FK constraints
        # ====================================================================
        print("\n" + "="*80)
        print("4. RENT_DEBT_LEDGER TABLE")
        print("="*80)
        
        if not dry_run:
            cur.execute(f"CREATE TABLE rent_debt_ledger_backup_{timestamp} AS SELECT * FROM rent_debt_ledger")
            print(f"✅ Backup: rent_debt_ledger_backup_{timestamp}")
        
        cur.execute("""
            SELECT 
                vendor_name,
                transaction_date,
                transaction_type,
                charge_amount,
                payment_amount,
                array_agg(id ORDER BY id) as ids
            FROM rent_debt_ledger
            GROUP BY vendor_name, transaction_date, transaction_type, charge_amount, payment_amount
            HAVING COUNT(*) > 1
        """)
        
        rent_groups = cur.fetchall()
        print(f"\nFound {len(rent_groups)} rent_debt_ledger duplicate groups")
        
        total_rent_deleted = 0
        
        for vendor, date, ttype, charge, payment, ids in rent_groups:
            keep_id = ids[0]
            delete_ids = ids[1:]
            
            if not dry_run:
                cur.execute("DELETE FROM rent_debt_ledger WHERE id = ANY(%s)", (delete_ids,))
                deleted = cur.rowcount
                total_rent_deleted += deleted
        
        print(f"📊 Rent Ledger: Deleted {total_rent_deleted}")
        
        # ====================================================================
        # 5. BANKING_TRANSACTIONS - Handle all FK constraints
        # ====================================================================
        print("\n" + "="*80)
        print("5. BANKING_TRANSACTIONS TABLE")
        print("="*80)
        
        if not dry_run:
            cur.execute(f"CREATE TABLE banking_transactions_backup_{timestamp} AS SELECT * FROM banking_transactions")
            print(f"✅ Backup: banking_transactions_backup_{timestamp}")
        
        cur.execute("""
            SELECT 
                transaction_date,
                account_number,
                description,
                debit_amount,
                credit_amount,
                array_agg(transaction_id ORDER BY transaction_id) as ids
            FROM banking_transactions
            GROUP BY transaction_date, account_number, description, debit_amount, credit_amount
            HAVING COUNT(*) > 1
        """)
        
        banking_groups = cur.fetchall()
        print(f"\nFound {len(banking_groups)} banking duplicate groups")
        
        total_banking_deleted = 0
        total_banking_links_updated = 0
        total_receipt_links_updated = 0
        total_payment_links_updated_2 = 0
        
        for date, acct, desc, debit, credit, ids in banking_groups[:10]:  # Process first 10 as test
            keep_id = ids[0]
            delete_ids = ids[1:]
            
            print(f"\n  {date} | {acct} | DR ${debit or 0:.2f} CR ${credit or 0:.2f}")
            print(f"    Keep: {keep_id}, Delete: {delete_ids[:5]}{'...' if len(delete_ids) > 5 else ''}")
            
            # Check and update banking_receipt_matching_ledger
            cur.execute("""
                SELECT COUNT(*) 
                FROM banking_receipt_matching_ledger 
                WHERE banking_transaction_id = ANY(%s)
            """, (delete_ids,))
            
            receipt_link_count = cur.fetchone()[0]
            
            if receipt_link_count > 0:
                print(f"    Found {receipt_link_count} banking_receipt_matching_ledger links")
                if not dry_run:
                    cur.execute("""
                        UPDATE banking_receipt_matching_ledger
                        SET banking_transaction_id = %s
                        WHERE banking_transaction_id = ANY(%s)
                    """, (keep_id, delete_ids))
                    total_receipt_links_updated += cur.rowcount
            
            # Check and update banking_payment_links
            cur.execute("""
                SELECT COUNT(*) 
                FROM banking_payment_links 
                WHERE banking_transaction_id = ANY(%s)
            """, (delete_ids,))
            
            payment_link_count = cur.fetchone()[0]
            
            if payment_link_count > 0:
                print(f"    Found {payment_link_count} banking_payment_links")
                if not dry_run:
                    cur.execute("""
                        UPDATE banking_payment_links
                        SET banking_transaction_id = %s
                        WHERE banking_transaction_id = ANY(%s)
                    """, (keep_id, delete_ids))
                    total_payment_links_updated_2 += cur.rowcount
            
            # Delete duplicates
            if not dry_run:
                cur.execute("DELETE FROM banking_transactions WHERE transaction_id = ANY(%s)", (delete_ids,))
                deleted = cur.rowcount
                total_banking_deleted += deleted
                print(f"    ✅ Deleted {deleted} transactions")
        
        if len(banking_groups) > 10:
            print(f"\n... and {len(banking_groups) - 10} more banking groups")
            if not dry_run:
                print("Run script again to process remaining banking groups")
        
        print(f"\n📊 Banking Summary (first 10 groups):")
        print(f"   Deleted: {total_banking_deleted}")
        print(f"   Receipt links updated: {total_receipt_links_updated}")
        print(f"   Payment links updated: {total_payment_links_updated_2}")
        
        # ====================================================================
        # COMMIT OR ROLLBACK
        # ====================================================================
        if dry_run:
            conn.rollback()
            print("\n⚠️ DRY RUN - No changes committed")
        else:
            conn.commit()
            print("\n✅ ALL CHANGES COMMITTED")
        
        # ====================================================================
        # FINAL SUMMARY
        # ====================================================================
        print("\n" + "="*80)
        print("FINAL SUMMARY")
        print("="*80)
        print(f"Payments deleted:         {total_payment_deleted}")
        print(f"Payment links updated:    {total_payment_links_updated}")
        print(f"Charter charges deleted:  {total_charges_deleted}")
        print(f"Journal deleted:          {1 if not dry_run else 0}")
        print(f"Rent ledger deleted:      {total_rent_deleted}")
        print(f"Banking deleted (batch):  {total_banking_deleted}")
        print(f"Banking receipt links:    {total_receipt_links_updated}")
        print(f"Banking payment links:    {total_payment_links_updated_2}")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERROR: {e}")
        print("Transaction rolled back")
        raise
    
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    dry_run = '--write' not in sys.argv
    deduplicate_with_fk_handling(dry_run=dry_run)
