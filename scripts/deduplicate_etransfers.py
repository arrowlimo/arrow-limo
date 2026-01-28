#!/usr/bin/env python3
"""
Deduplicate e-transfers based on transaction reference numbers.

Identifies duplicates where reference_number matches, keeping the first occurrence
and removing subsequent duplicates.

Usage:
    python deduplicate_etransfers.py --dry-run
    python deduplicate_etransfers.py --write --backup
"""

import os
import sys
import psycopg2
from datetime import datetime

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'almsdata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '***REMOVED***')

DRY_RUN = '--write' not in sys.argv
CREATE_BACKUP = '--backup' in sys.argv

def get_conn():
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)

def create_backup(cur):
    """Create backup table before deletion."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'etransfer_transactions_backup_{timestamp}'
    
    cur.execute(f"""
        CREATE TABLE {backup_table} AS
        SELECT * FROM etransfer_transactions
    """)
    
    return backup_table

def find_duplicates_by_reference(cur):
    """Find duplicates based on reference_number."""
    
    # Find reference numbers that appear more than once
    cur.execute("""
        SELECT 
            reference_number,
            COUNT(*) as dup_count,
            ARRAY_AGG(etransfer_id ORDER BY etransfer_id) as all_ids,
            ARRAY_AGG(transaction_date ORDER BY etransfer_id) as all_dates,
            ARRAY_AGG(amount ORDER BY etransfer_id) as all_amounts,
            ARRAY_AGG(direction ORDER BY etransfer_id) as all_directions
        FROM etransfer_transactions
        WHERE reference_number IS NOT NULL
        AND reference_number != ''
        GROUP BY reference_number
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC, reference_number
    """)
    
    return cur.fetchall()

def find_duplicates_by_banking_description(cur):
    """Find duplicates where banking descriptions contain same e-transfer number."""
    
    cur.execute("""
        WITH banking_refs AS (
            SELECT 
                et.etransfer_id,
                et.transaction_date,
                et.amount,
                et.direction,
                bt.description,
                SUBSTRING(bt.description FROM 'E-TRANSFER[# ]+([0-9]+)') as extracted_ref
            FROM etransfer_transactions et
            JOIN banking_transactions bt ON et.banking_transaction_id = bt.transaction_id
            WHERE bt.description ~ 'E-TRANSFER[# ]+[0-9]+'
        )
        SELECT 
            extracted_ref,
            COUNT(*) as dup_count,
            ARRAY_AGG(etransfer_id ORDER BY etransfer_id) as all_ids,
            ARRAY_AGG(transaction_date ORDER BY etransfer_id) as all_dates,
            ARRAY_AGG(amount ORDER BY etransfer_id) as all_amounts,
            ARRAY_AGG(direction ORDER BY etransfer_id) as all_directions,
            ARRAY_AGG(description ORDER BY etransfer_id) as all_descriptions
        FROM banking_refs
        WHERE extracted_ref IS NOT NULL
        GROUP BY extracted_ref
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC, extracted_ref
    """)
    
    return cur.fetchall()

def find_duplicates_by_email_event(cur):
    """Find duplicates pointing to same email event."""
    
    cur.execute("""
        SELECT 
            email_event_id,
            COUNT(*) as dup_count,
            ARRAY_AGG(etransfer_id ORDER BY etransfer_id) as all_ids,
            ARRAY_AGG(transaction_date ORDER BY etransfer_id) as all_dates,
            ARRAY_AGG(amount ORDER BY etransfer_id) as all_amounts,
            ARRAY_AGG(direction ORDER BY etransfer_id) as all_directions
        FROM etransfer_transactions
        WHERE email_event_id IS NOT NULL
        GROUP BY email_event_id
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC, email_event_id
    """)
    
    return cur.fetchall()

def main():
    print("\n" + "="*100)
    print("E-TRANSFER DEDUPLICATION BY TRANSACTION NUMBER")
    print("="*100)
    print(f"Mode: {'DRY RUN' if DRY_RUN else 'WRITE'}")
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Get total count before deduplication
        cur.execute("SELECT COUNT(*) FROM etransfer_transactions")
        total_before = cur.fetchone()[0]
        print(f"\nTotal e-transfers before deduplication: {total_before:,}")
        
        # Find duplicates by reference_number
        print("\n" + "="*100)
        print("1. DUPLICATES BY REFERENCE NUMBER")
        print("="*100)
        
        ref_duplicates = find_duplicates_by_reference(cur)
        
        if ref_duplicates:
            print(f"\nFound {len(ref_duplicates)} reference numbers with duplicates:")
            print(f"\n{'Reference #':<20} | {'Count':>6} | {'IDs to Keep':<12} | {'IDs to Delete'}")
            print("-" * 100)
            
            ref_ids_to_delete = []
            total_ref_dups = 0
            
            for ref_num, dup_count, all_ids, all_dates, all_amounts, all_dirs in ref_duplicates[:20]:
                keep_id = all_ids[0]
                delete_ids = all_ids[1:]
                
                print(f"{ref_num:<20} | {dup_count:>6} | {keep_id:<12} | {', '.join(map(str, delete_ids))}")
                
                ref_ids_to_delete.extend(delete_ids)
                total_ref_dups += len(delete_ids)
            
            if len(ref_duplicates) > 20:
                print(f"... and {len(ref_duplicates) - 20} more reference numbers")
            
            print(f"\nTotal duplicates by reference number: {total_ref_dups:,}")
        else:
            print("\nNo duplicates found by reference_number")
            ref_ids_to_delete = []
        
        # Find duplicates by banking description transaction number
        print("\n" + "="*100)
        print("2. DUPLICATES BY BANKING E-TRANSFER NUMBER")
        print("="*100)
        
        banking_duplicates = find_duplicates_by_banking_description(cur)
        
        if banking_duplicates:
            print(f"\nFound {len(banking_duplicates)} e-transfer numbers with duplicates:")
            print(f"\n{'E-Transfer #':<15} | {'Count':>6} | {'IDs to Keep':<12} | {'IDs to Delete'}")
            print("-" * 100)
            
            banking_ids_to_delete = []
            total_banking_dups = 0
            
            for etrans_num, dup_count, all_ids, all_dates, all_amounts, all_dirs, all_descs in banking_duplicates[:20]:
                keep_id = all_ids[0]
                delete_ids = all_ids[1:]
                
                print(f"{etrans_num:<15} | {dup_count:>6} | {keep_id:<12} | {', '.join(map(str, delete_ids))}")
                
                banking_ids_to_delete.extend(delete_ids)
                total_banking_dups += len(delete_ids)
            
            if len(banking_duplicates) > 20:
                print(f"... and {len(banking_duplicates) - 20} more e-transfer numbers")
            
            print(f"\nTotal duplicates by banking e-transfer number: {total_banking_dups:,}")
        else:
            print("\nNo duplicates found by banking e-transfer number")
            banking_ids_to_delete = []
        
        # Find duplicates by email event
        print("\n" + "="*100)
        print("3. DUPLICATES BY EMAIL EVENT ID")
        print("="*100)
        
        email_duplicates = find_duplicates_by_email_event(cur)
        
        if email_duplicates:
            print(f"\nFound {len(email_duplicates)} email events with duplicates:")
            print(f"\n{'Email Event ID':<15} | {'Count':>6} | {'IDs to Keep':<12} | {'IDs to Delete'}")
            print("-" * 100)
            
            email_ids_to_delete = []
            total_email_dups = 0
            
            for email_id, dup_count, all_ids, all_dates, all_amounts, all_dirs in email_duplicates[:20]:
                keep_id = all_ids[0]
                delete_ids = all_ids[1:]
                
                print(f"{email_id:<15} | {dup_count:>6} | {keep_id:<12} | {', '.join(map(str, delete_ids))}")
                
                email_ids_to_delete.extend(delete_ids)
                total_email_dups += len(delete_ids)
            
            if len(email_duplicates) > 20:
                print(f"... and {len(email_duplicates) - 20} more email events")
            
            print(f"\nTotal duplicates by email event: {total_email_dups:,}")
        else:
            print("\nNo duplicates found by email event ID")
            email_ids_to_delete = []
        
        # Combine all IDs to delete (remove duplicates in the delete list itself)
        all_ids_to_delete = list(set(ref_ids_to_delete + banking_ids_to_delete + email_ids_to_delete))
        
        print("\n" + "="*100)
        print("DEDUPLICATION SUMMARY")
        print("="*100)
        print(f"\nTotal unique IDs to delete: {len(all_ids_to_delete):,}")
        
        if all_ids_to_delete:
            # Show breakdown by category
            cur.execute("""
                SELECT 
                    category,
                    COUNT(*) as count,
                    SUM(amount) as total
                FROM etransfer_transactions
                WHERE etransfer_id = ANY(%s)
                GROUP BY category
                ORDER BY count DESC
            """, (all_ids_to_delete,))
            
            print(f"\nDuplicates by category:")
            for cat, count, total in cur.fetchall():
                cat_name = cat if cat else 'Uncategorized'
                print(f"  {cat_name}: {count:,} records, ${total or 0:,.2f}")
            
            # Delete duplicates
            if not DRY_RUN:
                if CREATE_BACKUP:
                    print("\nCreating backup...")
                    backup_table = create_backup(cur)
                    print(f"  ✓ Backup created: {backup_table}")
                
                print(f"\nDeleting {len(all_ids_to_delete):,} duplicate e-transfers...")
                cur.execute("""
                    DELETE FROM etransfer_transactions
                    WHERE etransfer_id = ANY(%s)
                """, (all_ids_to_delete,))
                
                deleted_count = cur.rowcount
                print(f"  ✓ Deleted {deleted_count:,} records")
                
                conn.commit()
                
                # Get final count
                cur.execute("SELECT COUNT(*) FROM etransfer_transactions")
                total_after = cur.fetchone()[0]
                
                print(f"\nTotal e-transfers after deduplication: {total_after:,}")
                print(f"Reduction: {total_before - total_after:,} records ({(total_before - total_after) / total_before * 100:.1f}%)")
                
                print("\n[SUCCESS] Deduplication completed.")
            else:
                print("\n[DRY RUN] No changes made to database.")
                print(f"Would delete {len(all_ids_to_delete):,} duplicate records.")
                print("\nRun with --write to apply changes.")
                print("Add --backup flag to create backup table before deletion.")
                conn.rollback()
        else:
            print("\nNo duplicates found - database is clean!")
            conn.rollback()
        
    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()
    
    print("\n" + "="*100)

if __name__ == '__main__':
    main()
