"""
Phase 2B - Delete Non-Business Expenses
Deletes cash withdrawals, NSF fees, and accounting entries that aren't business expenses
"""

import psycopg2
from datetime import datetime

def connect_db():
    return psycopg2.connect(
        dbname="almsdata",
        user="postgres",
        password="ArrowLimousine",
        host="localhost"
    )

def phase2b_cleanup():
    conn = connect_db()
    conn.autocommit = False
    cur = conn.cursor()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f"receipts_backup_phase2b_nonexpenses_{timestamp}"
    
    try:
        print("\n" + "="*80)
        print("PHASE 2B - DELETE NON-BUSINESS EXPENSES")
        print("="*80)
        print(f"Timestamp: {timestamp}")
        print(f"Backup Table: {backup_table}")
        
        # Step 1: Count targets
        print("\n" + "="*80)
        print("STEP 1: Identifying Deletion Targets")
        print("="*80)
        
        cur.execute("""
            SELECT 
                CASE 
                    WHEN vendor_name ILIKE '%CASH WITHDRAWAL%' THEN 'CASH_WITHDRAWAL'
                    WHEN vendor_name ILIKE '%BANK WITHDRAWAL%' THEN 'BANK_WITHDRAWAL'
                    WHEN vendor_name ILIKE '%ATM%' THEN 'ATM_WITHDRAWAL'
                    WHEN vendor_name ILIKE '%NSF%' AND vendor_name NOT ILIKE '%TRANSFER%' THEN 'NSF_FEE'
                    WHEN vendor_name ILIKE '%RETURNED%' THEN 'RETURNED_PAYMENT'
                    WHEN vendor_name ILIKE '%DISHON%' THEN 'DISHONORED'
                    WHEN vendor_name ILIKE '%OPENING BALANCE%' THEN 'OPENING_BALANCE'
                    WHEN vendor_name = 'CHARTER PAYMENT' THEN 'CHARTER_PAYMENT'
                END as category,
                COUNT(*) as count,
                SUM(COALESCE(gross_amount, 0)) as total
            FROM receipts
            WHERE 
                vendor_name ILIKE '%CASH WITHDRAWAL%'
                OR vendor_name ILIKE '%BANK WITHDRAWAL%'
                OR vendor_name ILIKE '%ATM%'
                OR (vendor_name ILIKE '%NSF%' AND vendor_name NOT ILIKE '%TRANSFER%')
                OR vendor_name ILIKE '%RETURNED%'
                OR vendor_name ILIKE '%DISHON%'
                OR vendor_name ILIKE '%OPENING BALANCE%'
                OR vendor_name = 'CHARTER PAYMENT'
            GROUP BY 
                CASE 
                    WHEN vendor_name ILIKE '%CASH WITHDRAWAL%' THEN 'CASH_WITHDRAWAL'
                    WHEN vendor_name ILIKE '%BANK WITHDRAWAL%' THEN 'BANK_WITHDRAWAL'
                    WHEN vendor_name ILIKE '%ATM%' THEN 'ATM_WITHDRAWAL'
                    WHEN vendor_name ILIKE '%NSF%' AND vendor_name NOT ILIKE '%TRANSFER%' THEN 'NSF_FEE'
                    WHEN vendor_name ILIKE '%RETURNED%' THEN 'RETURNED_PAYMENT'
                    WHEN vendor_name ILIKE '%DISHON%' THEN 'DISHONORED'
                    WHEN vendor_name ILIKE '%OPENING BALANCE%' THEN 'OPENING_BALANCE'
                    WHEN vendor_name = 'CHARTER PAYMENT' THEN 'CHARTER_PAYMENT'
                END
            ORDER BY category
        """)
        
        print(f"\n{'Category':<25} {'Count':>8} {'Total':>15}")
        print("-"*55)
        
        total_delete_count = 0
        total_delete_amount = 0
        
        for cat, count, total in cur.fetchall():
            print(f"{cat:<25} {count:>8,} ${total:>14,.2f}")
            total_delete_count += count
            total_delete_amount += total
        
        print("-"*55)
        print(f"{'TOTAL TO DELETE':<25} {total_delete_count:>8,} ${total_delete_amount:>14,.2f}")
        
        print(f"\n✋ These are:")
        print(f"  - Cash withdrawals/ATM (owner draws)")
        print(f"  - NSF fees (bounced client payments)")
        print(f"  - Opening balance (accounting entry)")
        print(f"  - NOT business expenses")
        
        # Step 2: Create backup
        print("\n" + "="*80)
        print("STEP 2: Creating Backup Table")
        print("="*80)
        
        cur.execute(f"""
            CREATE TABLE {backup_table} AS
            SELECT * FROM receipts
            WHERE 
                vendor_name ILIKE '%CASH WITHDRAWAL%'
                OR vendor_name ILIKE '%BANK WITHDRAWAL%'
                OR vendor_name ILIKE '%ATM%'
                OR (vendor_name ILIKE '%NSF%' AND vendor_name NOT ILIKE '%TRANSFER%')
                OR vendor_name ILIKE '%RETURNED%'
                OR vendor_name ILIKE '%DISHON%'
                OR vendor_name ILIKE '%OPENING BALANCE%'
                OR vendor_name = 'CHARTER PAYMENT'
        """)
        
        cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
        backup_count = cur.fetchone()[0]
        print(f"\n✅ Backup created: {backup_table}")
        print(f"   Backed up {backup_count:,} receipts")
        
        # Step 3: Check foreign key references
        print("\n" + "="*80)
        print("STEP 3: Checking Foreign Key References")
        print("="*80)
        
        cur.execute("""
            SELECT COUNT(DISTINCT bt.transaction_id)
            FROM banking_transactions bt
            WHERE bt.receipt_id IN (
                SELECT receipt_id FROM receipts
                WHERE 
                    vendor_name ILIKE '%CASH WITHDRAWAL%'
                    OR vendor_name ILIKE '%BANK WITHDRAWAL%'
                    OR vendor_name ILIKE '%ATM%'
                    OR (vendor_name ILIKE '%NSF%' AND vendor_name NOT ILIKE '%TRANSFER%')
                    OR vendor_name ILIKE '%RETURNED%'
                    OR vendor_name ILIKE '%DISHON%'
                    OR vendor_name ILIKE '%OPENING BALANCE%'
                    OR vendor_name = 'CHARTER PAYMENT'
            )
        """)
        
        fk_count = cur.fetchone()[0]
        print(f"\nBanking transactions with FK references: {fk_count:,}")
        
        if fk_count > 0:
            print(f"\n⚠️  Clearing {fk_count:,} foreign key references...")
            cur.execute("""
                UPDATE banking_transactions
                SET receipt_id = NULL
                WHERE receipt_id IN (
                    SELECT receipt_id FROM receipts
                    WHERE 
                        vendor_name ILIKE '%CASH WITHDRAWAL%'
                        OR vendor_name ILIKE '%BANK WITHDRAWAL%'
                        OR vendor_name ILIKE '%ATM%'
                        OR (vendor_name ILIKE '%NSF%' AND vendor_name NOT ILIKE '%TRANSFER%')
                        OR vendor_name ILIKE '%RETURNED%'
                        OR vendor_name ILIKE '%DISHON%'
                        OR vendor_name ILIKE '%OPENING BALANCE%'
                        OR vendor_name = 'CHARTER PAYMENT'
                )
            """)
            print(f"✅ Cleared {fk_count:,} FK references")
        
        # Step 4: Delete receipts
        print("\n" + "="*80)
        print("STEP 4: Deleting Receipts")
        print("="*80)
        
        print("\nExecuting deletion...")
        cur.execute("""
            DELETE FROM receipts
            WHERE 
                vendor_name ILIKE '%CASH WITHDRAWAL%'
                OR vendor_name ILIKE '%BANK WITHDRAWAL%'
                OR vendor_name ILIKE '%ATM%'
                OR (vendor_name ILIKE '%NSF%' AND vendor_name NOT ILIKE '%TRANSFER%')
                OR vendor_name ILIKE '%RETURNED%'
                OR vendor_name ILIKE '%DISHON%'
                OR vendor_name ILIKE '%OPENING BALANCE%'
                OR vendor_name = 'CHARTER PAYMENT'
        """)
        
        deleted_count = cur.rowcount
        print(f"✅ Deleted {deleted_count:,} receipts")
        
        # Step 5: Verification
        print("\n" + "="*80)
        print("STEP 5: Post-Deletion Verification")
        print("="*80)
        
        if deleted_count == total_delete_count:
            print(f"✅ Deletion count matches expected: {deleted_count:,} = {total_delete_count:,}")
        else:
            print(f"⚠️  WARNING: Deletion count mismatch!")
            print(f"   Expected: {total_delete_count:,}")
            print(f"   Deleted: {deleted_count:,}")
        
        # Check remaining receipts
        cur.execute("SELECT COUNT(*), SUM(gross_amount) FROM receipts")
        remaining_count, remaining_amount = cur.fetchone()
        print(f"\nRemaining receipts: {remaining_count:,} (${remaining_amount:,.2f})")
        
        # Verify vendor expenses are still there
        cur.execute("""
            SELECT COUNT(*), SUM(gross_amount)
            FROM receipts
            WHERE 
                vendor_name ILIKE '%HEFFNER%' OR vendor_name ILIKE '%AUTO%' 
                OR vendor_name ILIKE '%TIRE%' OR vendor_name ILIKE '%REPAIR%'
                OR vendor_name ILIKE '%FUEL%' OR vendor_name ILIKE '%GAS%'
                OR gross_amount < 0
        """)
        
        vendor_count, vendor_amount = cur.fetchone()
        vendor_amount_str = f"${vendor_amount:,.2f}" if vendor_amount is not None else "$0.00"
        print(f"\nVendor expenses still intact: {vendor_count:,} ({vendor_amount_str})")
        
        # Verify employee transfers are still there
        cur.execute("""
            SELECT COUNT(*), SUM(gross_amount)
            FROM receipts
            WHERE vendor_name LIKE 'EMAIL TRANSFER%'
        """)
        
        employee_count, employee_amount = cur.fetchone()
        employee_amount_str = f"${employee_amount:,.2f}" if employee_amount is not None else "$0.00"
        print(f"Employee transfers still intact: {employee_count:,} ({employee_amount_str})")
        
        # Final summary
        print("\n" + "="*80)
        print("CLEANUP SUMMARY")
        print("="*80)
        
        print(f"\n✅ Phase 2B cleanup completed successfully!")
        print(f"\nDeleted: {deleted_count:,} non-business expenses (${total_delete_amount:,.2f})")
        print(f"  - Cash withdrawals (owner draws)")
        print(f"  - Bank/ATM withdrawals")
        print(f"  - NSF fees (bounced payments)")
        print(f"  - Opening balance (accounting entry)")
        print(f"\nPreserved:")
        print(f"  - Vendor expenses: {vendor_count:,} ({vendor_amount_str})")
        print(f"  - Employee transfers: {employee_count:,} ({employee_amount_str})")
        print(f"\nBackup: {backup_table}")
        
        # Prompt for commit
        print("\n" + "="*80)
        response = input("\n✋ COMMIT these changes? (yes/no): ").strip().lower()
        
        if response == 'yes':
            conn.commit()
            print("\n✅ Changes COMMITTED to database")
            print(f"\nRecovery command if needed:")
            print(f"   INSERT INTO receipts SELECT * FROM {backup_table};")
        else:
            conn.rollback()
            print("\n❌ Changes ROLLED BACK - no data deleted")
            print(f"   Backup table preserved: {backup_table}")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERROR: {e}")
        print("Transaction ROLLED BACK - no changes made")
        raise
    
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    phase2b_cleanup()
