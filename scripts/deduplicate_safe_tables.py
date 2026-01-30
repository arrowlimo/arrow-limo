"""
Simple deduplication focusing only on tables WITHOUT complex FK constraints

This avoids the banking_transactions and payments FK complexity by focusing on:
- charter_charges: No FK constraints
- journal: No FK constraints (standalone table)
- rent_debt_ledger: No FK constraints (standalone table)

We'll handle payments and banking_transactions separately after understanding full FK chains.
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

def main():
    dry_run = '--write' not in sys.argv
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        print("="*80)
        print("SIMPLE DEDUPLICATION - SAFE TABLES ONLY")
        print("="*80)
        print("\nTarget tables with NO FK constraints:")
        print("  - charter_charges: 44 duplicates")
        print("  - journal: 1 duplicate")
        print("  - rent_debt_ledger: 3 duplicates")
        print("  TOTAL: 48 duplicates")
        print(f"\nMode: {'🔥 WRITE' if not dry_run else '⚠️ DRY RUN'}")
        
        total_deleted = 0
        
        # ================================================================
        # 1. CHARTER_CHARGES
        # ================================================================
        print("\n" + "="*80)
        print("1. CHARTER_CHARGES")
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
        
        groups = cur.fetchall()
        print(f"\nFound {len(groups)} duplicate groups")
        
        charges_deleted = 0
        for charter_id, desc, amt, ids in groups:
            keep_id = ids[0]
            delete_ids = ids[1:]
            
            print(f"  Charter {charter_id or 'None'} | {desc} | ${amt:.2f} - keeping {keep_id}, deleting {len(delete_ids)}")
            
            if not dry_run:
                cur.execute("DELETE FROM charter_charges WHERE charge_id = ANY(%s)", (delete_ids,))
                charges_deleted += cur.rowcount
        
        print(f"\n📊 Charter Charges: Deleted {charges_deleted}")
        total_deleted += charges_deleted
        
        # ================================================================
        # 2. JOURNAL
        # ================================================================
        print("\n" + "="*80)
        print("2. JOURNAL")
        print("="*80)
        
        if not dry_run:
            cur.execute(f"CREATE TABLE journal_backup_{timestamp} AS SELECT * FROM journal")
            print(f"✅ Backup: journal_backup_{timestamp}")
        
        print("\n  Deleting journal_id 936 (duplicate of 935)")
        
        journal_deleted = 0
        if not dry_run:
            cur.execute("DELETE FROM journal WHERE journal_id = 936")
            journal_deleted = cur.rowcount
        
        print(f"\n📊 Journal: Deleted {journal_deleted}")
        total_deleted += journal_deleted
        
        # ================================================================
        # 3. RENT_DEBT_LEDGER
        # ================================================================
        print("\n" + "="*80)
        print("3. RENT_DEBT_LEDGER")
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
        
        groups = cur.fetchall()
        print(f"\nFound {len(groups)} duplicate groups")
        
        rent_deleted = 0
        for vendor, date, ttype, charge, payment, ids in groups:
            keep_id = ids[0]
            delete_ids = ids[1:]
            
            amt = charge if charge else payment
            print(f"  {vendor} | {date} | {ttype} | ${amt:.2f} - keeping {keep_id}, deleting {len(delete_ids)}")
            
            if not dry_run:
                cur.execute("DELETE FROM rent_debt_ledger WHERE id = ANY(%s)", (delete_ids,))
                rent_deleted += cur.rowcount
        
        print(f"\n📊 Rent Debt Ledger: Deleted {rent_deleted}")
        total_deleted += rent_deleted
        
        # ================================================================
        # COMMIT OR ROLLBACK
        # ================================================================
        if dry_run:
            conn.rollback()
            print("\n⚠️ DRY RUN - No changes committed")
        else:
            conn.commit()
            print("\n✅ ALL CHANGES COMMITTED")
        
        # ================================================================
        # VERIFICATION
        # ================================================================
        print("\n" + "="*80)
        print("VERIFICATION")
        print("="*80)
        
        # Check charter_charges
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT charter_id, description, amount
                FROM charter_charges
                GROUP BY charter_id, description, amount
                HAVING COUNT(*) > 1
            ) sub
        """)
        if cur.fetchone()[0] == 0:
            print("✅ charter_charges: CLEAN")
        
        # Check journal
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT "Date", "Account", "Memo/Description", "Debit", "Credit"
                FROM journal
                GROUP BY "Date", "Account", "Memo/Description", "Debit", "Credit"
                HAVING COUNT(*) > 1
            ) sub
        """)
        if cur.fetchone()[0] == 0:
            print("✅ journal: CLEAN")
        
        # Check rent_debt_ledger
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT vendor_name, transaction_date, transaction_type, charge_amount, payment_amount
                FROM rent_debt_ledger
                GROUP BY vendor_name, transaction_date, transaction_type, charge_amount, payment_amount
                HAVING COUNT(*) > 1
            ) sub
        """)
        if cur.fetchone()[0] == 0:
            print("✅ rent_debt_ledger: CLEAN")
        
        # ================================================================
        # FINAL SUMMARY
        # ================================================================
        print("\n" + "="*80)
        print("FINAL SUMMARY")
        print("="*80)
        print(f"Charter charges deleted: {charges_deleted}")
        print(f"Journal deleted:         {journal_deleted}")
        print(f"Rent ledger deleted:     {rent_deleted}")
        print(f"-" * 40)
        print(f"TOTAL DELETED:           {total_deleted}")
        
        print("\n📝 NOTE: Skipped payments and banking_transactions due to complex FK constraints")
        print("   Run scripts/find_all_fk_constraints.py to see the full FK chain")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERROR: {e}")
        raise
    
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
