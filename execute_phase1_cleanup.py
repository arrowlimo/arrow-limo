"""
Phase 1 Cleanup - Delete Processor Settlements and Duplicate Client Payments
WITH PROTECTION FOR 2019 MANUAL ENTRIES

Deletes:
1. Square deposits (205 receipts, $131K) - Payment processor settlements
2. Client e-transfer payments (673 receipts, $336K) - Already in charter_payments
3. Charter payment entries (235 receipts, $108K) - Duplicates

Safeguards:
- Only deletes banking imports (created_from_banking=TRUE OR banking_transaction_id IS NOT NULL)
- Protects 2019 manual entries (5 e-transfer payments)
- Creates backup table before deletion
- Clears foreign key references first
- Transaction with verification
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

def phase1_cleanup():
    conn = connect_db()
    conn.autocommit = False
    cur = conn.cursor()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f"receipts_backup_phase1_cleanup_{timestamp}"
    
    try:
        print("\n" + "="*80)
        print("PHASE 1 CLEANUP - Processor Settlements & Duplicate Client Payments")
        print("="*80)
        print(f"Timestamp: {timestamp}")
        print(f"Backup Table: {backup_table}")
        
        # Step 1: Identify deletion targets
        print("\n" + "="*80)
        print("STEP 1: Identifying Deletion Targets")
        print("="*80)
        
        cur.execute("""
            SELECT 
                COUNT(*) as total_count,
                SUM(gross_amount) as total_amount,
                COUNT(CASE WHEN vendor_name ILIKE '%SQUARE%' AND gross_amount > 0 THEN 1 END) as square_count,
                SUM(CASE WHEN vendor_name ILIKE '%SQUARE%' AND gross_amount > 0 THEN gross_amount ELSE 0 END) as square_amount,
                COUNT(CASE WHEN vendor_name ILIKE '%E-TRANSFER%' AND gross_amount > 0 THEN 1 END) as etransfer_count,
                SUM(CASE WHEN vendor_name ILIKE '%E-TRANSFER%' AND gross_amount > 0 THEN gross_amount ELSE 0 END) as etransfer_amount,
                COUNT(CASE WHEN vendor_name = 'CHARTER PAYMENT' THEN 1 END) as charter_payment_count,
                SUM(CASE WHEN vendor_name = 'CHARTER PAYMENT' THEN gross_amount ELSE 0 END) as charter_payment_amount
            FROM receipts
            WHERE (
                (vendor_name ILIKE '%SQUARE%' AND gross_amount > 0)
                OR (vendor_name ILIKE '%E-TRANSFER%' AND gross_amount > 0)
                OR (vendor_name = 'CHARTER PAYMENT')
            )
            AND (
                created_from_banking = TRUE 
                OR banking_transaction_id IS NOT NULL
            )
        """)
        
        total_count, total_amount, sq_count, sq_amount, et_count, et_amount, cp_count, cp_amount = cur.fetchone()
        
        print(f"\nTotal receipts to delete: {total_count:,}")
        print(f"Total amount: ${total_amount:,.2f}")
        print(f"\nBreakdown:")
        print(f"  1. Square deposits: {sq_count:,} receipts (${sq_amount:,.2f})")
        print(f"  2. E-transfer client payments: {et_count:,} receipts (${et_amount:,.2f})")
        print(f"  3. Charter payment entries: {cp_count:,} receipts (${cp_amount:,.2f})")
        
        # Check 2019 protection
        print("\n" + "="*80)
        print("STEP 2: Verifying 2019 Manual Entry Protection")
        print("="*80)
        
        cur.execute("""
            SELECT 
                COUNT(*) as manual_2019_protected
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = 2019
              AND (
                  (vendor_name ILIKE '%SQUARE%' AND gross_amount > 0)
                  OR (vendor_name ILIKE '%E-TRANSFER%' AND gross_amount > 0)
                  OR (vendor_name = 'CHARTER PAYMENT')
              )
              AND (created_from_banking = FALSE OR created_from_banking IS NULL)
              AND banking_transaction_id IS NULL
        """)
        
        manual_2019 = cur.fetchone()[0]
        print(f"\n2019 Manual entries protected from deletion: {manual_2019:,}")
        
        if manual_2019 > 0:
            cur.execute("""
                SELECT 
                    receipt_id,
                    receipt_date,
                    vendor_name,
                    gross_amount
                FROM receipts
                WHERE EXTRACT(YEAR FROM receipt_date) = 2019
                  AND (
                      (vendor_name ILIKE '%SQUARE%' AND gross_amount > 0)
                      OR (vendor_name ILIKE '%E-TRANSFER%' AND gross_amount > 0)
                      OR (vendor_name = 'CHARTER PAYMENT')
                  )
                  AND (created_from_banking = FALSE OR created_from_banking IS NULL)
                  AND banking_transaction_id IS NULL
                ORDER BY receipt_date
            """)
            
            print(f"\n{'ID':<10} {'Date':<12} {'Vendor':<40} {'Amount':>12}")
            print("-"*80)
            for rid, rdate, vendor, amount in cur.fetchall():
                print(f"{rid:<10} {str(rdate):<12} {vendor[:40]:<40} ${amount:>11,.2f}")
            print(f"\n✅ These {manual_2019} manual entries will be PROTECTED")
        else:
            print("✅ No manual 2019 entries in deletion target categories")
        
        # Step 3: Create backup
        print("\n" + "="*80)
        print("STEP 3: Creating Backup Table")
        print("="*80)
        
        cur.execute(f"""
            CREATE TABLE {backup_table} AS
            SELECT * FROM receipts
            WHERE (
                (vendor_name ILIKE '%SQUARE%' AND gross_amount > 0)
                OR (vendor_name ILIKE '%E-TRANSFER%' AND gross_amount > 0)
                OR (vendor_name = 'CHARTER PAYMENT')
            )
            AND (
                created_from_banking = TRUE 
                OR banking_transaction_id IS NOT NULL
            )
        """)
        
        cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
        backup_count = cur.fetchone()[0]
        print(f"\n✅ Backup created: {backup_table}")
        print(f"   Backed up {backup_count:,} receipts")
        
        # Step 4: Check foreign key references
        print("\n" + "="*80)
        print("STEP 4: Checking Foreign Key References")
        print("="*80)
        
        cur.execute("""
            SELECT COUNT(DISTINCT bt.transaction_id)
            FROM banking_transactions bt
            WHERE bt.receipt_id IN (
                SELECT receipt_id FROM receipts
                WHERE (
                    (vendor_name ILIKE '%SQUARE%' AND gross_amount > 0)
                    OR (vendor_name ILIKE '%E-TRANSFER%' AND gross_amount > 0)
                    OR (vendor_name = 'CHARTER PAYMENT')
                )
                AND (
                    created_from_banking = TRUE 
                    OR banking_transaction_id IS NOT NULL
                )
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
                    WHERE (
                        (vendor_name ILIKE '%SQUARE%' AND gross_amount > 0)
                        OR (vendor_name ILIKE '%E-TRANSFER%' AND gross_amount > 0)
                        OR (vendor_name = 'CHARTER PAYMENT')
                    )
                    AND (
                        created_from_banking = TRUE 
                        OR banking_transaction_id IS NOT NULL
                    )
                )
            """)
            print(f"✅ Cleared {fk_count:,} FK references")
        
        # Step 5: Delete receipts
        print("\n" + "="*80)
        print("STEP 5: Deleting Receipts")
        print("="*80)
        
        print("\nExecuting deletion...")
        cur.execute("""
            DELETE FROM receipts
            WHERE (
                (vendor_name ILIKE '%SQUARE%' AND gross_amount > 0)
                OR (vendor_name ILIKE '%E-TRANSFER%' AND gross_amount > 0)
                OR (vendor_name = 'CHARTER PAYMENT')
            )
            AND (
                created_from_banking = TRUE 
                OR banking_transaction_id IS NOT NULL
            )
        """)
        
        deleted_count = cur.rowcount
        print(f"✅ Deleted {deleted_count:,} receipts")
        
        # Step 6: Verification
        print("\n" + "="*80)
        print("STEP 6: Post-Deletion Verification")
        print("="*80)
        
        # Verify deletion counts match
        if deleted_count == total_count:
            print(f"✅ Deletion count matches expected: {deleted_count:,} = {total_count:,}")
        else:
            print(f"⚠️  WARNING: Deletion count mismatch!")
            print(f"   Expected: {total_count:,}")
            print(f"   Deleted: {deleted_count:,}")
        
        # Check remaining receipts
        cur.execute("SELECT COUNT(*) FROM receipts")
        remaining_count = cur.fetchone()[0]
        print(f"\nRemaining receipts: {remaining_count:,}")
        
        # Verify 2019 manual entries still exist
        cur.execute("""
            SELECT COUNT(*)
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = 2019
              AND (
                  (vendor_name ILIKE '%E-TRANSFER%' AND gross_amount > 0)
                  OR (vendor_name ILIKE '%SQUARE%' AND gross_amount > 0)
                  OR (vendor_name = 'CHARTER PAYMENT')
              )
              AND (created_from_banking = FALSE OR created_from_banking IS NULL)
              AND banking_transaction_id IS NULL
        """)
        
        manual_2019_after = cur.fetchone()[0]
        print(f"\n2019 manual entries still protected: {manual_2019_after:,}")
        
        if manual_2019_after == manual_2019:
            print(f"✅ All {manual_2019} manual 2019 entries protected!")
        else:
            print(f"⚠️  WARNING: Manual entry count changed!")
            print(f"   Before: {manual_2019}")
            print(f"   After: {manual_2019_after}")
        
        # Final summary
        print("\n" + "="*80)
        print("CLEANUP SUMMARY")
        print("="*80)
        
        print(f"\n✅ Phase 1 cleanup completed successfully!")
        print(f"\nDeleted: {deleted_count:,} receipts")
        print(f"  - Square deposits: {sq_count:,}")
        print(f"  - E-transfer payments: {et_count:,}")
        print(f"  - Charter payment entries: {cp_count:,}")
        print(f"\nProtected: {manual_2019:,} manual 2019 entries")
        print(f"Remaining receipts: {remaining_count:,}")
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
    phase1_cleanup()
