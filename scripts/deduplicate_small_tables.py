"""
Cleanup duplicates from small tables: payments, charter_charges, journal, rent_debt_ledger

Created: 2025-11-26
Purpose: Remove remaining 62 duplicates from 4 small tables after successful receipts/payroll cleanup
"""

import psycopg2
from datetime import datetime
import sys

def get_db_connection():
    """Standard PostgreSQL connection"""
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def create_backup(cur, table_name, timestamp):
    """Create timestamped backup table"""
    backup_name = f"{table_name}_backup_{timestamp}"
    cur.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM {table_name}")
    print(f"✅ Backup created: {backup_name}")
    return backup_name

def deduplicate_payments(cur, timestamp):
    """
    Remove 14 duplicate payments
    - 11 duplicates: Reserve 017720, $102.00 (LMS import artifacts)
    - 4 duplicates: Reserve 019209, $500.00 (LMS import artifacts)
    - 2 duplicates: Reserve 013690, $1,240.00 (LMS import artifacts)
    
    Keep: Earliest payment_id
    """
    print("\n" + "="*80)
    print("PAYMENTS TABLE - Deduplication")
    print("="*80)
    
    # Create backup
    create_backup(cur, 'payments', timestamp)
    
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
    print(f"\nFound {len(dup_groups)} duplicate groups")
    
    total_deleted = 0
    for rsv, amt, date, ids, count in dup_groups:
        # Keep first ID (earliest), delete rest
        keep_id = ids[0]
        delete_ids = ids[1:]
        
        print(f"  Reserve {rsv} | {date} | ${amt:.2f} - keeping ID {keep_id}, deleting {len(delete_ids)} copies")
        
        # Delete duplicates
        cur.execute("DELETE FROM payments WHERE payment_id = ANY(%s)", (delete_ids,))
        deleted = cur.rowcount
        total_deleted += deleted
    
    print(f"\n✅ Total deleted from payments: {total_deleted}")
    return total_deleted

def deduplicate_charter_charges(cur, timestamp):
    """
    Remove 44 duplicate charter_charges
    - Most are NULL charter_id with same description and amount
    - Keep: Earliest charge_id
    """
    print("\n" + "="*80)
    print("CHARTER_CHARGES TABLE - Deduplication")
    print("="*80)
    
    # Create backup
    create_backup(cur, 'charter_charges', timestamp)
    
    # Find duplicates
    cur.execute("""
        SELECT 
            charter_id,
            description,
            amount,
            array_agg(charge_id ORDER BY charge_id) as ids,
            COUNT(*) as dup_count
        FROM charter_charges
        GROUP BY charter_id, description, amount
        HAVING COUNT(*) > 1
    """)
    
    dup_groups = cur.fetchall()
    print(f"\nFound {len(dup_groups)} duplicate groups")
    
    total_deleted = 0
    for charter_id, desc, amt, ids, count in dup_groups:
        # Keep first ID (earliest), delete rest
        keep_id = ids[0]
        delete_ids = ids[1:]
        
        charter_str = f"Charter {charter_id}" if charter_id else "Charter None"
        print(f"  {charter_str} | {desc} | ${amt:.2f} - keeping ID {keep_id}, deleting {len(delete_ids)} copies")
        
        # Delete duplicates
        cur.execute("DELETE FROM charter_charges WHERE charge_id = ANY(%s)", (delete_ids,))
        deleted = cur.rowcount
        total_deleted += deleted
    
    print(f"\n✅ Total deleted from charter_charges: {total_deleted}")
    return total_deleted

def deduplicate_journal(cur, timestamp):
    """
    Remove 1 duplicate journal entry
    - Date: 4/2/2012
    - Account: 1090 Bank Shareholder
    - Amount: $10.00 CR
    - IDs: 935, 936 (keep 935, delete 936)
    """
    print("\n" + "="*80)
    print("JOURNAL TABLE - Deduplication")
    print("="*80)
    
    # Create backup
    create_backup(cur, 'journal', timestamp)
    
    # Specific deletion for the one duplicate
    print("\n  Deleting journal_id 936 (duplicate of 935)")
    cur.execute("DELETE FROM journal WHERE journal_id = 936")
    deleted = cur.rowcount
    
    print(f"\n✅ Total deleted from journal: {deleted}")
    return deleted

def deduplicate_rent_debt_ledger(cur, timestamp):
    """
    Remove 3 duplicate rent_debt_ledger entries
    - Fibrenew Office Rent
    - Date: 2022-02-02
    - Type: PAYMENT
    - Amount: $800.00
    - IDs: 586, 587, 588, 589 (keep 586, delete 587, 588, 589)
    """
    print("\n" + "="*80)
    print("RENT_DEBT_LEDGER TABLE - Deduplication")
    print("="*80)
    
    # Create backup
    create_backup(cur, 'rent_debt_ledger', timestamp)
    
    # Find duplicates
    cur.execute("""
        SELECT 
            entry_date,
            entry_type,
            amount,
            array_agg(id ORDER BY id) as ids,
            COUNT(*) as dup_count
        FROM rent_debt_ledger
        GROUP BY entry_date, entry_type, amount
        HAVING COUNT(*) > 1
    """)
    
    dup_groups = cur.fetchall()
    print(f"\nFound {len(dup_groups)} duplicate groups")
    
    total_deleted = 0
    for date, etype, amt, ids, count in dup_groups:
        # Keep first ID (earliest), delete rest
        keep_id = ids[0]
        delete_ids = ids[1:]
        
        print(f"  {date} | {etype} | ${amt:.2f} - keeping ID {keep_id}, deleting {len(delete_ids)} copies")
        
        # Delete duplicates
        cur.execute("DELETE FROM rent_debt_ledger WHERE id = ANY(%s)", (delete_ids,))
        deleted = cur.rowcount
        total_deleted += deleted
    
    print(f"\n✅ Total deleted from rent_debt_ledger: {total_deleted}")
    return total_deleted

def verify_cleanup(cur):
    """Verify all duplicates are gone"""
    print("\n" + "="*80)
    print("VERIFICATION - Checking for remaining duplicates")
    print("="*80)
    
    tables = ['payments', 'charter_charges', 'journal', 'rent_debt_ledger']
    all_clean = True
    
    for table in tables:
        if table == 'journal':
            # Journal uses quoted column names
            cur.execute("""
                SELECT COUNT(*) FROM (
                    SELECT "Date", "Account", "Memo/Description", "Debit", "Credit"
                    FROM journal
                    GROUP BY "Date", "Account", "Memo/Description", "Debit", "Credit"
                    HAVING COUNT(*) > 1
                ) sub
            """)
        elif table == 'payments':
            cur.execute("""
                SELECT COUNT(*) FROM (
                    SELECT reserve_number, amount, payment_date
                    FROM payments
                    GROUP BY reserve_number, amount, payment_date
                    HAVING COUNT(*) > 1
                ) sub
            """)
        elif table == 'charter_charges':
            cur.execute("""
                SELECT COUNT(*) FROM (
                    SELECT charter_id, description, amount
                    FROM charter_charges
                    GROUP BY charter_id, description, amount
                    HAVING COUNT(*) > 1
                ) sub
            """)
        elif table == 'rent_debt_ledger':
            cur.execute("""
                SELECT COUNT(*) FROM (
                    SELECT entry_date, entry_type, amount
                    FROM rent_debt_ledger
                    GROUP BY entry_date, entry_type, amount
                    HAVING COUNT(*) > 1
                ) sub
            """)
        
        dup_count = cur.fetchone()[0]
        if dup_count == 0:
            print(f"  ✅ {table}: CLEAN (0 duplicates)")
        else:
            print(f"  ⚠️ {table}: STILL HAS DUPLICATES ({dup_count} groups)")
            all_clean = False
    
    return all_clean

def main():
    """Main execution"""
    print("="*80)
    print("SMALL TABLES DEDUPLICATION")
    print("="*80)
    print("\nTarget tables:")
    print("  - payments: 14 duplicates")
    print("  - charter_charges: 44 duplicates")
    print("  - journal: 1 duplicate")
    print("  - rent_debt_ledger: 3 duplicates")
    print("  TOTAL: 62 duplicates to remove")
    
    # Check for --write flag
    dry_run = '--write' not in sys.argv
    
    if dry_run:
        print("\n⚠️ DRY RUN MODE - No changes will be made")
        print("Add --write flag to execute deletions")
        return
    
    print("\n🔥 WRITE MODE - Changes will be committed")
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Deduplicate each table
        p_deleted = deduplicate_payments(cur, timestamp)
        c_deleted = deduplicate_charter_charges(cur, timestamp)
        j_deleted = deduplicate_journal(cur, timestamp)
        r_deleted = deduplicate_rent_debt_ledger(cur, timestamp)
        
        # Commit all changes
        conn.commit()
        print("\n✅ All changes committed to database")
        
        # Verify cleanup
        all_clean = verify_cleanup(cur)
        
        # Final summary
        total_deleted = p_deleted + c_deleted + j_deleted + r_deleted
        print("\n" + "="*80)
        print("FINAL SUMMARY")
        print("="*80)
        print(f"Payments deleted:        {p_deleted}")
        print(f"Charter charges deleted: {c_deleted}")
        print(f"Journal deleted:         {j_deleted}")
        print(f"Rent ledger deleted:     {r_deleted}")
        print(f"-" * 40)
        print(f"TOTAL DELETED:           {total_deleted}")
        print(f"\nVerification: {'✅ ALL CLEAN' if all_clean else '⚠️ DUPLICATES REMAIN'}")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERROR: {e}")
        print("Transaction rolled back - no changes made")
        raise
    
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
