"""
Fix MoneyMart Visa Card Load Receipts - CRA Compliant Accounting
================================================================
MoneyMart transactions are prepaid Visa card loads = ASSET TRANSFERS, not expenses

PROPER ACCOUNTING:
  When loading the card:
    DR: 1135 Prepaid Visa Cards (Asset)
    CR: 1010 Scotia Bank Main (Cash)
  
  When spending from the card:
    DR: Appropriate expense account (e.g., 5110 Fuel)
    CR: 1135 Prepaid Visa Cards (Asset)

This script:
1. Creates GL account 1135 "Prepaid Visa Cards" if needed
2. Updates all MoneyMart receipts to proper categorization
3. Sets is_transfer = TRUE (these are asset transfers)
4. Creates audit trail for CRA compliance
"""
import psycopg2
import os
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def create_gl_account_1135(cur):
    """Create GL account 1135 for Prepaid Visa Cards if it doesn't exist"""
    
    # Check if 1135 exists
    cur.execute("SELECT account_code FROM chart_of_accounts WHERE account_code = '1135'")
    if cur.fetchone():
        print("✅ GL Account 1135 (Prepaid Visa Cards) already exists")
        return False
    
    # Create the account
    cur.execute("""
        INSERT INTO chart_of_accounts (
            account_code,
            account_name,
            account_type,
            qb_account_type,
            parent_account,
            account_level,
            is_header_account,
            normal_balance,
            description,
            is_active,
            created_at
        ) VALUES (
            '1135',
            'Prepaid Visa Cards',
            'Asset',
            'OtherCurrentAsset',
            '1100',
            2,
            FALSE,
            'DEBIT',
            'MoneyMart prepaid Visa card balances - Asset account for card loads',
            TRUE,
            CURRENT_TIMESTAMP
        )
    """)
    
    print("✅ Created GL Account 1135 - Prepaid Visa Cards (Asset)")
    return True

def fix_moneymart_receipts(cur, dry_run=True):
    """Update all MoneyMart receipts to proper categorization"""
    
    # Find all MoneyMart receipts
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            category,
            gl_account_code,
            expense_account,
            is_transfer
        FROM receipts 
        WHERE UPPER(vendor_name) LIKE '%MONEY%MART%' 
           OR UPPER(vendor_name) LIKE '%MONEYMART%'
        ORDER BY receipt_date
    """)
    
    receipts = cur.fetchall()
    
    print(f"\n{'='*100}")
    print(f"MONEYMART PREPAID CARD LOAD RECLASSIFICATION")
    print(f"{'='*100}")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE UPDATE (committing changes)'}")
    print(f"Total receipts to update: {len(receipts)}")
    print(f"{'='*100}\n")
    
    updated_count = 0
    total_amount = 0
    
    for receipt in receipts:
        receipt_id, receipt_date, vendor_name, gross_amount, old_category, old_gl, old_expense_acct, is_transfer = receipt
        total_amount += float(gross_amount or 0)
        
        needs_update = (
            old_category not in ('Prepaid Card Load', 'PREPAID CARD LOAD') or
            old_gl != '1135' or
            not is_transfer
        )
        
        if needs_update:
            print(f"Receipt {receipt_id:6d} | {receipt_date} | ${gross_amount:8.2f}")
            print(f"  OLD: Category='{old_category}' | GL={old_gl or 'NULL'} | Transfer={is_transfer}")
            print(f"  NEW: Category='Prepaid Card Load' | GL=1135 | Transfer=TRUE")
            
            if not dry_run:
                cur.execute("""
                    UPDATE receipts
                    SET 
                        category = 'Prepaid Card Load',
                        gl_account_code = '1135',
                        gl_account_name = 'Prepaid Visa Cards',
                        gl_subcategory = 'Asset Transfer',
                        is_transfer = TRUE,
                        expense_account = 'PREPAID VISA CARDS - ASSET',
                        deductible_status = 'NOT_DEDUCTIBLE',
                        business_personal = 'BUSINESS',
                        comment = COALESCE(comment || E'\\n', '') || 
                                  'RECLASSIFIED: ' || CURRENT_DATE || ' - MoneyMart prepaid Visa card load = Asset transfer (Cash→Prepaid Card), not expense. CRA compliant.'
                    WHERE receipt_id = %s
                """, (receipt_id,))
                updated_count += 1
            else:
                updated_count += 1
            
            print()
    
    print(f"{'='*100}")
    print(f"SUMMARY")
    print(f"{'='*100}")
    print(f"Total MoneyMart receipts analyzed: {len(receipts)}")
    print(f"Receipts needing update: {updated_count}")
    print(f"Total prepaid card loads: ${total_amount:,.2f}")
    print(f"Mode: {'DRY RUN - No changes made' if dry_run else 'LIVE UPDATE - Changes committed'}")
    print(f"{'='*100}\n")
    
    return updated_count

def create_audit_log(cur, updated_count, total_amount):
    """Create audit trail entry for CRA compliance"""
    
    audit_entry = f"""
MONEYMART PREPAID VISA CARD RECLASSIFICATION - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
================================================================================

ACTION: Reclassified {updated_count} MoneyMart transactions as prepaid Visa card loads
TOTAL AMOUNT: ${total_amount:,.2f}
ACCOUNTING TREATMENT: Asset transfer (Cash → Prepaid Visa Cards)

OLD CATEGORIZATION:
  - Various categories (TRANSFERS, BANKING, Unknown, etc.)
  - Various GL codes (mostly 1010, 5400, 4130, etc.)
  - Incorrectly treated as expenses or revenue in some cases

NEW CATEGORIZATION:
  - Category: Prepaid Card Load
  - GL Code: 1135 (Prepaid Visa Cards - Asset)
  - is_transfer: TRUE
  - deductible_status: NOT_DEDUCTIBLE (asset transfer, not expense)

CRA COMPLIANCE:
  Loading a prepaid Visa card is NOT a deductible business expense.
  It is a conversion of one asset (cash) into another asset (prepaid card balance).
  Only the actual purchases made WITH the card are deductible expenses.

REFERENCES:
  - GL Account 1135: Prepaid Visa Cards (OtherCurrentAsset)
  - Parent Account: 1100 Current Assets
  - Normal Balance: DEBIT

SCRIPT: fix_moneymart_prepaid_card_loads.py
EXECUTED BY: Automated data correction - CRA compliance review
"""
    
    print(audit_entry)
    
    # Save audit log to file
    audit_file = f"l:/limo/reports/MONEYMART_RECLASSIFICATION_AUDIT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(audit_file, 'w', encoding='utf-8') as f:
        f.write(audit_entry)
    
    print(f"✅ Audit log saved: {audit_file}")

def main():
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║  MONEYMART PREPAID VISA CARD RECLASSIFICATION - CRA COMPLIANCE FIX          ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    try:
        # Step 1: Create GL account 1135 if needed
        print("\n[STEP 1] Creating GL Account 1135 (Prepaid Visa Cards)...")
        gl_created = create_gl_account_1135(cur)
        
        # Step 2: Dry run first
        print("\n[STEP 2] DRY RUN - Analyzing receipts...")
        updated_count_dry = fix_moneymart_receipts(cur, dry_run=True)
        
        if updated_count_dry == 0:
            print("\n✅ All MoneyMart receipts are already correctly categorized!")
            cur.close()
            conn.close()
            return
        
        # Step 3: Ask for confirmation
        print(f"\n⚠️  READY TO UPDATE {updated_count_dry} receipts")
        print("    This will:")
        print("    - Set category to 'Prepaid Card Load'")
        print("    - Set GL code to 1135 (Prepaid Visa Cards - Asset)")
        print("    - Mark as is_transfer = TRUE")
        print("    - Add audit comment to each receipt")
        print("    - Mark as NOT_DEDUCTIBLE (asset transfer)")
        
        response = input("\nProceed with LIVE UPDATE? (yes/no): ").strip().lower()
        
        if response != 'yes':
            print("\n❌ Operation cancelled by user")
            cur.close()
            conn.close()
            return
        
        # Step 4: Live update
        print("\n[STEP 3] LIVE UPDATE - Applying changes...")
        updated_count = fix_moneymart_receipts(cur, dry_run=False)
        
        # Get total amount
        cur.execute("""
            SELECT SUM(gross_amount) 
            FROM receipts 
            WHERE UPPER(vendor_name) LIKE '%MONEY%MART%' 
               OR UPPER(vendor_name) LIKE '%MONEYMART%'
        """)
        total_amount = float(cur.fetchone()[0] or 0)
        
        # Step 5: Commit changes
        conn.commit()
        print(f"\n✅ COMMITTED: {updated_count} receipts updated successfully")
        
        # Step 6: Create audit log
        print("\n[STEP 4] Creating audit trail...")
        create_audit_log(cur, updated_count, total_amount)
        
        print("\n" + "="*100)
        print("✅ MONEYMART RECLASSIFICATION COMPLETE - CRA COMPLIANT")
        print("="*100)
        print(f"  - {updated_count} receipts reclassified as prepaid card loads")
        print(f"  - Total amount: ${total_amount:,.2f}")
        print(f"  - GL Account 1135 (Prepaid Visa Cards) {'created' if gl_created else 'verified'}")
        print(f"  - All marked as asset transfers (NOT expenses)")
        print("="*100 + "\n")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERROR: {e}")
        print("⚠️  Transaction rolled back - no changes made")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
