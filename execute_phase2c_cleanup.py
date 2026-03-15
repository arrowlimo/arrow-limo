"""
Phase 2C - Delete Additional Non-Business Items
Deletes cash withdrawals, deposits, and credit card payments
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

def phase2c_cleanup():
    conn = connect_db()
    conn.autocommit = False
    cur = conn.cursor()
    
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_table = f"receipts_backup_phase2c_misc_{timestamp}"
        
        print("="*80)
        print("PHASE 2C - DELETE ADDITIONAL NON-BUSINESS ITEMS")
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
                    WHEN vendor_name ILIKE '%BRANCH TRANSACTION WITHDRAWAL%' THEN 'BRANCH_WITHDRAWAL'
                    WHEN vendor_name ILIKE '%WITHDRAWAL IBB%' THEN 'IBB_WITHDRAWAL'
                    WHEN vendor_name ILIKE '%CASH DEPOSIT%' THEN 'CASH_DEPOSIT'
                    WHEN vendor_name ILIKE '%DEPOSIT%' AND vendor_name NOT ILIKE '%CUSTOMER DEPOSIT%' THEN 'DEPOSIT'
                    WHEN vendor_name ILIKE '%CUSTOMER DEPOSIT%' THEN 'CUSTOMER_DEPOSIT'
                    WHEN vendor_name ILIKE '%AMERICAN EXPRESS PAYMENT%' THEN 'AMEX_PAYMENT'
                    WHEN vendor_name ILIKE '%CREDIT CARD PAYMENT%' THEN 'CC_PAYMENT'
                    WHEN vendor_name ILIKE '%CAPITAL ONE%PAYMENT%' THEN 'CAPITAL_ONE_PAYMENT'
                END as category,
                COUNT(*) as count,
                SUM(COALESCE(gross_amount, 0)) as total
            FROM receipts
            WHERE 
                vendor_name ILIKE '%BRANCH TRANSACTION WITHDRAWAL%'
                OR vendor_name ILIKE '%WITHDRAWAL IBB%'
                OR vendor_name ILIKE '%DEPOSIT%'
                OR vendor_name ILIKE '%AMERICAN EXPRESS PAYMENT%'
                OR vendor_name ILIKE '%CREDIT CARD PAYMENT%'
                OR vendor_name ILIKE '%CAPITAL ONE%PAYMENT%'
            GROUP BY 
                CASE 
                    WHEN vendor_name ILIKE '%BRANCH TRANSACTION WITHDRAWAL%' THEN 'BRANCH_WITHDRAWAL'
                    WHEN vendor_name ILIKE '%WITHDRAWAL IBB%' THEN 'IBB_WITHDRAWAL'
                    WHEN vendor_name ILIKE '%CASH DEPOSIT%' THEN 'CASH_DEPOSIT'
                    WHEN vendor_name ILIKE '%DEPOSIT%' AND vendor_name NOT ILIKE '%CUSTOMER DEPOSIT%' THEN 'DEPOSIT'
                    WHEN vendor_name ILIKE '%CUSTOMER DEPOSIT%' THEN 'CUSTOMER_DEPOSIT'
                    WHEN vendor_name ILIKE '%AMERICAN EXPRESS PAYMENT%' THEN 'AMEX_PAYMENT'
                    WHEN vendor_name ILIKE '%CREDIT CARD PAYMENT%' THEN 'CC_PAYMENT'
                    WHEN vendor_name ILIKE '%CAPITAL ONE%PAYMENT%' THEN 'CAPITAL_ONE_PAYMENT'
                END
            ORDER BY category
        """)
        
        print(f"\n{'Category':<25} {'Count':>8} {'Total':>15}")
        print("-"*55)
        
        total_delete_count = 0
        total_delete_amount = 0
        
        for row in cur.fetchall():
            category, count, total = row
            print(f"{category:<25} {count:>8,} ${total:>13,.2f}")
            total_delete_count += count
            total_delete_amount += total
        
        print("-"*55)
        print(f"{'TOTAL TO DELETE':<25} {total_delete_count:>8,} ${total_delete_amount:>13,.2f}")
        
        print(f"\n✋ These are:")
        print(f"  - Cash withdrawals (owner draws)")
        print(f"  - Deposits (cash/check deposits to bank)")
        print(f"  - Credit card payments (transfers to pay cards)")
        print(f"  - NOT business expenses")
        
        # Step 2: Create backup
        print("\n" + "="*80)
        print("STEP 2: Creating Backup Table")
        print("="*80)
        
        cur.execute(f"""
            CREATE TABLE {backup_table} AS
            SELECT * FROM receipts
            WHERE 
                vendor_name ILIKE '%BRANCH TRANSACTION WITHDRAWAL%'
                OR vendor_name ILIKE '%WITHDRAWAL IBB%'
                OR vendor_name ILIKE '%DEPOSIT%'
                OR vendor_name ILIKE '%AMERICAN EXPRESS PAYMENT%'
                OR vendor_name ILIKE '%CREDIT CARD PAYMENT%'
                OR vendor_name ILIKE '%CAPITAL ONE%PAYMENT%'
        """)
        
        cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
        backup_count = cur.fetchone()[0]
        print(f"\n✅ Backup created: {backup_table}")
        print(f"   Backed up {backup_count:,} receipts")
        
        # Step 3: Check foreign keys
        print("\n" + "="*80)
        print("STEP 3: Checking Foreign Key References")
        print("="*80)
        
        cur.execute("""
            SELECT COUNT(DISTINCT bt.transaction_id)
            FROM banking_transactions bt
            WHERE bt.receipt_id IN (
                SELECT receipt_id FROM receipts
                WHERE 
                    vendor_name ILIKE '%BRANCH TRANSACTION WITHDRAWAL%'
                    OR vendor_name ILIKE '%WITHDRAWAL IBB%'
                    OR vendor_name ILIKE '%DEPOSIT%'
                    OR vendor_name ILIKE '%AMERICAN EXPRESS PAYMENT%'
                    OR vendor_name ILIKE '%CREDIT CARD PAYMENT%'
                    OR vendor_name ILIKE '%CAPITAL ONE%PAYMENT%'
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
                        vendor_name ILIKE '%BRANCH TRANSACTION WITHDRAWAL%'
                        OR vendor_name ILIKE '%WITHDRAWAL IBB%'
                        OR vendor_name ILIKE '%DEPOSIT%'
                        OR vendor_name ILIKE '%AMERICAN EXPRESS PAYMENT%'
                        OR vendor_name ILIKE '%CREDIT CARD PAYMENT%'
                        OR vendor_name ILIKE '%CAPITAL ONE%PAYMENT%'
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
                vendor_name ILIKE '%BRANCH TRANSACTION WITHDRAWAL%'
                OR vendor_name ILIKE '%WITHDRAWAL IBB%'
                OR vendor_name ILIKE '%DEPOSIT%'
                OR vendor_name ILIKE '%AMERICAN EXPRESS PAYMENT%'
                OR vendor_name ILIKE '%CREDIT CARD PAYMENT%'
                OR vendor_name ILIKE '%CAPITAL ONE%PAYMENT%'
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
            print(f"   Actual: {deleted_count:,}")
        
        # Check remaining receipts
        cur.execute("SELECT COUNT(*), SUM(gross_amount) FROM receipts")
        remaining_count, remaining_amount = cur.fetchone()
        print(f"\nRemaining receipts: {remaining_count:,} (${remaining_amount:,.2f})")
        
        # Verify employee transfers are still there
        cur.execute("""
            SELECT COUNT(*), SUM(gross_amount)
            FROM receipts
            WHERE vendor_name LIKE 'EMAIL TRANSFER%'
        """)
        
        employee_count, employee_amount = cur.fetchone()
        employee_amount_str = f"${employee_amount:,.2f}" if employee_amount else "$0.00"
        print(f"Employee transfers still intact: {employee_count:,} ({employee_amount_str})")
        
        # Final summary
        print("\n" + "="*80)
        print("CLEANUP SUMMARY")
        print("="*80)
        
        print(f"\n✅ Phase 2C cleanup completed successfully!")
        print(f"\nDeleted: {deleted_count:,} non-business items (${total_delete_amount:,.2f})")
        print(f"  - Cash withdrawals (owner draws)")
        print(f"  - Deposits (bank deposits)")
        print(f"  - Credit card payments (transfers)")
        print(f"\nPreserved:")
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
    phase2c_cleanup()
