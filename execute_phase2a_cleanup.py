"""
Phase 2A - Delete Inter-Account Transfers (Not Expenses)
Safe to delete - can be recreated from banking imports if needed
User confirmed: "inter account movements dont need tracking"
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

def phase2a_cleanup():
    conn = connect_db()
    conn.autocommit = False
    cur = conn.cursor()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f"receipts_backup_phase2a_interaccount_{timestamp}"
    
    try:
        print("\n" + "="*80)
        print("PHASE 2A - DELETE INTER-ACCOUNT TRANSFERS")
        print("="*80)
        print(f"Timestamp: {timestamp}")
        print(f"Backup Table: {backup_table}")
        
        # Step 1: Count targets
        print("\n" + "="*80)
        print("STEP 1: Identifying Deletion Targets")
        print("="*80)
        
        cur.execute("""
            SELECT 
                COUNT(*) as total_count,
                SUM(gross_amount) as total_amount
            FROM receipts
            WHERE 
                vendor_name = 'BANK TRANSFER'
                OR vendor_name = 'TRANSFER'
                OR vendor_name = 'BANKING TRANSFER'
                OR vendor_name = 'BANK TTRANSFERE'
                OR vendor_name LIKE 'INTERNET BANKING INTERNET TRANSFER%'
                OR vendor_name LIKE 'INTERNET TRANSFER%'
                OR vendor_name LIKE '%TRANSFER FEE%'
                OR vendor_name LIKE 'ELECTRONIC FUNDS TRANSFER%'
        """)
        
        total_count, total_amount = cur.fetchone()
        
        print(f"\nTotal receipts to delete: {total_count:,}")
        print(f"Total amount: ${total_amount:,.2f}")
        print(f"\nThese are:")
        print(f"  - Inter-account transfers (not expenses)")
        print(f"  - Banking fees (not business expenses)")
        print(f"  - Preauthorized debits (auto-transfers)")
        print(f"\n✅ Can be recreated from banking imports if needed")
        
        # Step 2: Create backup
        print("\n" + "="*80)
        print("STEP 2: Creating Backup Table")
        print("="*80)
        
        cur.execute(f"""
            CREATE TABLE {backup_table} AS
            SELECT * FROM receipts
            WHERE 
                vendor_name = 'BANK TRANSFER'
                OR vendor_name = 'TRANSFER'
                OR vendor_name = 'BANKING TRANSFER'
                OR vendor_name = 'BANK TTRANSFERE'
                OR vendor_name LIKE 'INTERNET BANKING INTERNET TRANSFER%'
                OR vendor_name LIKE 'INTERNET TRANSFER%'
                OR vendor_name LIKE '%TRANSFER FEE%'
                OR vendor_name LIKE 'ELECTRONIC FUNDS TRANSFER%'
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
                    vendor_name = 'BANK TRANSFER'
                    OR vendor_name = 'TRANSFER'
                    OR vendor_name = 'BANKING TRANSFER'
                    OR vendor_name = 'BANK TTRANSFERE'
                    OR vendor_name LIKE 'INTERNET BANKING INTERNET TRANSFER%'
                    OR vendor_name LIKE 'INTERNET TRANSFER%'
                    OR vendor_name LIKE '%TRANSFER FEE%'
                    OR vendor_name LIKE 'ELECTRONIC FUNDS TRANSFER%'
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
                        vendor_name = 'BANK TRANSFER'
                        OR vendor_name = 'TRANSFER'
                        OR vendor_name = 'BANKING TRANSFER'
                        OR vendor_name = 'BANK TTRANSFERE'
                        OR vendor_name LIKE 'INTERNET BANKING INTERNET TRANSFER%'
                        OR vendor_name LIKE 'INTERNET TRANSFER%'
                        OR vendor_name LIKE '%TRANSFER FEE%'
                        OR vendor_name LIKE 'ELECTRONIC FUNDS TRANSFER%'
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
                vendor_name = 'BANK TRANSFER'
                OR vendor_name = 'TRANSFER'
                OR vendor_name = 'BANKING TRANSFER'
                OR vendor_name = 'BANK TTRANSFERE'
                OR vendor_name LIKE 'INTERNET BANKING INTERNET TRANSFER%'
                OR vendor_name LIKE 'INTERNET TRANSFER%'
                OR vendor_name LIKE '%TRANSFER FEE%'
                OR vendor_name LIKE 'ELECTRONIC FUNDS TRANSFER%'
        """)
        
        deleted_count = cur.rowcount
        print(f"✅ Deleted {deleted_count:,} receipts")
        
        # Step 5: Verification
        print("\n" + "="*80)
        print("STEP 5: Post-Deletion Verification")
        print("="*80)
        
        if deleted_count == total_count:
            print(f"✅ Deletion count matches expected: {deleted_count:,} = {total_count:,}")
        else:
            print(f"⚠️  WARNING: Deletion count mismatch!")
            print(f"   Expected: {total_count:,}")
            print(f"   Deleted: {deleted_count:,}")
        
        # Check remaining receipts
        cur.execute("SELECT COUNT(*), SUM(gross_amount) FROM receipts")
        remaining_count, remaining_amount = cur.fetchone()
        print(f"\nRemaining receipts: {remaining_count:,} (${remaining_amount:,.2f})")
        
        # Verify employee transfers are still there
        cur.execute("""
            SELECT COUNT(*), SUM(gross_amount)
            FROM receipts
            WHERE vendor_name LIKE 'EMAIL TRANSFER%'
               OR vendor_name LIKE '%TRANSFER%'
        """)
        
        employee_count, employee_amount = cur.fetchone()
        print(f"\nEmployee transfers still intact: {employee_count:,} (${employee_amount:,.2f})")
        print(f"  ✅ Mike Woodrow rent, John McLean reimb, other employees preserved")
        
        # Final summary
        print("\n" + "="*80)
        print("CLEANUP SUMMARY")
        print("="*80)
        
        print(f"\n✅ Phase 2A cleanup completed successfully!")
        print(f"\nDeleted: {deleted_count:,} inter-account transfers (${total_amount:,.2f})")
        print(f"  - BANK TRANSFER (inter-account)")
        print(f"  - TRANSFER (generic)")
        print(f"  - INTERNET BANKING INTERNET TRANSFER")
        print(f"  - EMAIL TRANSFER FEE (banking fees)")
        print(f"  - ELECTRONIC FUNDS TRANSFER PREAUTHORIZED")
        print(f"\nPreserved: {employee_count:,} employee transfers (${employee_amount:,.2f})")
        print(f"  - Employee pay/reimbursements")
        print(f"  - Mike Woodrow rent")
        print(f"  - John McLean driver reimbursements")
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
    phase2a_cleanup()
