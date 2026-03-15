"""
Fix Bank Fee Tracking Issues
1. Create receipts for banking transactions without receipts
2. Re-link orphaned receipts to banking transactions
"""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
    host="localhost"
)
conn.autocommit = False
cur = conn.cursor()

print("="*80)
print("FIX BANK FEE TRACKING")
print("="*80)

try:
    # TASK 1: Create receipts for banking transactions without receipts
    print("\n" + "="*80)
    print("TASK 1: CREATE RECEIPTS FOR MISSING BANK FEES")
    print("="*80)
    
    # Get banking transactions without receipts
    cur.execute("""
        SELECT 
            bt.transaction_id,
            bt.transaction_date,
            bt.description,
            bt.debit_amount,
            bt.vendor_extracted,
            bt.category
        FROM banking_transactions bt
        WHERE (bt.description ILIKE '%SERVICE CHARGE%'
            OR bt.description ILIKE '%BANK FEE%'
            OR bt.description ILIKE '%OVERDRAFT%'
            OR bt.description ILIKE '%NSF FEE%'
            OR bt.description ILIKE '%ACCOUNT FEE%'
            OR bt.description ILIKE '%MONTHLY FEE%'
            OR bt.description ILIKE '%INTERAC FEE%'
            OR bt.vendor_extracted ILIKE '%BANK FEE%'
            OR bt.vendor_extracted ILIKE '%SERVICE CHARGE%')
        AND bt.debit_amount IS NOT NULL
        AND bt.debit_amount > 0
        AND bt.receipt_id IS NULL
        ORDER BY bt.transaction_date
    """)
    
    missing_receipts = cur.fetchall()
    print(f"\nFound {len(missing_receipts)} banking transactions without receipts")
    
    created_count = 0
    created_amount = 0
    
    for trans_id, trans_date, description, amount, vendor, category in missing_receipts:
        # Determine vendor name
        if vendor:
            vendor_name = vendor
        elif 'NSF' in description.upper():
            vendor_name = 'NSF FEE'
        elif 'OVERDRAFT' in description.upper():
            vendor_name = 'OVERDRAFT FEE'
        elif 'SERVICE CHARGE' in description.upper():
            vendor_name = 'BANK SERVICE FEE'
        elif 'ACCOUNT FEE' in description.upper():
            vendor_name = 'ACCOUNT FEE'
        elif 'INTERAC' in description.upper():
            vendor_name = 'INTERAC FEE'
        else:
            vendor_name = 'BANK FEE'
        
        # Insert receipt
        cur.execute("""
            INSERT INTO receipts (
                receipt_date,
                vendor_name,
                gross_amount,
                category,
                gl_account_code,
                banking_transaction_id,
                created_from_banking,
                needs_review,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            RETURNING receipt_id
        """, (
            trans_date,
            vendor_name,
            amount,
            'Bank Fees',
            '5900',
            trans_id,
            True,
            False
        ))
        
        receipt_id = cur.fetchone()[0]
        
        # Update banking transaction with receipt_id
        cur.execute("""
            UPDATE banking_transactions
            SET receipt_id = %s
            WHERE transaction_id = %s
        """, (receipt_id, trans_id))
        
        created_count += 1
        created_amount += amount
        
        if created_count <= 10:
            print(f"  Created: {trans_date} - {vendor_name} - ${amount:.2f}")
    
    if created_count > 10:
        print(f"  ... and {created_count - 10} more")
    
    print(f"\n✅ Created {created_count} receipts (${created_amount:,.2f})")
    
    # TASK 2: Re-link orphaned receipts to banking transactions
    print("\n" + "="*80)
    print("TASK 2: RE-LINK ORPHANED RECEIPTS TO BANKING")
    print("="*80)
    
    # Get orphaned bank fee receipts
    cur.execute("""
        SELECT 
            r.receipt_id,
            r.receipt_date,
            r.vendor_name,
            r.gross_amount
        FROM receipts r
        WHERE (r.category = 'Bank Fees' 
           OR r.category = 'Bank Charges'
           OR r.category = 'bank_fees'
           OR r.gl_account_code = '5900')
        AND r.banking_transaction_id IS NULL
        AND r.created_from_banking = TRUE
        ORDER BY r.receipt_date
    """)
    
    orphaned_receipts = cur.fetchall()
    print(f"\nFound {len(orphaned_receipts)} receipts without banking links")
    
    linked_count = 0
    linked_amount = 0
    
    for receipt_id, receipt_date, vendor_name, amount in orphaned_receipts:
        # Try to find matching banking transaction
        # Match on date and amount (within $0.01)
        cur.execute("""
            SELECT transaction_id
            FROM banking_transactions
            WHERE transaction_date = %s
              AND ABS(COALESCE(debit_amount, 0) - %s) < 0.01
              AND receipt_id IS NULL
            LIMIT 1
        """, (receipt_date, amount))
        
        result = cur.fetchone()
        
        if result:
            trans_id = result[0]
            
            # Update receipt with banking link
            cur.execute("""
                UPDATE receipts
                SET banking_transaction_id = %s, updated_at = NOW()
                WHERE receipt_id = %s
            """, (trans_id, receipt_id))
            
            # Update banking transaction with receipt link
            cur.execute("""
                UPDATE banking_transactions
                SET receipt_id = %s
                WHERE transaction_id = %s
            """, (receipt_id, trans_id))
            
            linked_count += 1
            linked_amount += amount
            
            if linked_count <= 10:
                print(f"  Linked: {receipt_date} - {vendor_name} - ${amount:.2f}")
    
    if linked_count > 10:
        print(f"  ... and {linked_count - 10} more")
    
    print(f"\n✅ Linked {linked_count} receipts (${linked_amount:,.2f})")
    
    # Check if there are still orphaned receipts
    still_orphaned = len(orphaned_receipts) - linked_count
    if still_orphaned > 0:
        print(f"\n⚠️  {still_orphaned} receipts could not be auto-linked (no matching banking transaction)")
        print("   These may be manual entries or the banking transaction may have been deleted")
    
    # VERIFICATION
    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)
    
    # Check receipts
    cur.execute("""
        SELECT 
            COUNT(*) as count,
            SUM(gross_amount) as total,
            COUNT(CASE WHEN banking_transaction_id IS NOT NULL THEN 1 END) as with_link,
            COUNT(CASE WHEN banking_transaction_id IS NULL THEN 1 END) as no_link
        FROM receipts
        WHERE category = 'Bank Fees' 
           OR category = 'Bank Charges'
           OR category = 'bank_fees'
           OR gl_account_code = '5900'
    """)
    
    count, total, with_link, no_link = cur.fetchone()
    print(f"\nBank fee receipts: {count:,} (${total:,.2f})")
    print(f"  With banking link: {with_link:,}")
    print(f"  Without banking link: {no_link:,}")
    
    # Check banking transactions
    cur.execute("""
        SELECT 
            COUNT(*) as count,
            SUM(COALESCE(debit_amount, 0)) as total,
            COUNT(CASE WHEN receipt_id IS NOT NULL THEN 1 END) as has_receipt,
            COUNT(CASE WHEN receipt_id IS NULL THEN 1 END) as no_receipt
        FROM banking_transactions
        WHERE (description ILIKE '%SERVICE CHARGE%'
            OR description ILIKE '%BANK FEE%'
            OR description ILIKE '%OVERDRAFT%'
            OR description ILIKE '%NSF FEE%'
            OR description ILIKE '%ACCOUNT FEE%'
            OR description ILIKE '%MONTHLY FEE%'
            OR description ILIKE '%INTERAC FEE%'
            OR vendor_extracted ILIKE '%BANK FEE%'
            OR vendor_extracted ILIKE '%SERVICE CHARGE%')
        AND debit_amount IS NOT NULL
        AND debit_amount > 0
    """)
    
    bt_count, bt_total, bt_has_receipt, bt_no_receipt = cur.fetchone()
    print(f"\nBanking transactions: {bt_count:,} (${bt_total:,.2f})")
    print(f"  Linked to receipt: {bt_has_receipt:,}")
    print(f"  No receipt link: {bt_no_receipt:,}")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"""
Changes made:
  ✅ Created {created_count} new receipts (${created_amount:,.2f})
  ✅ Linked {linked_count} orphaned receipts (${linked_amount:,.2f})
  
Remaining issues:
  ⚠️  {no_link} receipts without banking link
  ⚠️  {bt_no_receipt} banking transactions without receipt
""")
    
    if bt_no_receipt == 0 and no_link == 0:
        print("🎉 All bank fees are fully tracked!")
    elif bt_no_receipt == 0:
        print("✅ All banking transactions have receipts")
        if no_link > 0:
            print(f"⚠️  {no_link} manual receipts remain unlinked (may be legitimate)")
    
    response = input("\n✋ COMMIT these changes? (yes/no): ").strip().lower()
    
    if response == 'yes':
        conn.commit()
        print("\n✅ Changes COMMITTED")
        print(f"\n📊 Total receipts created: {created_count}")
        print(f"📊 Total receipts linked: {linked_count}")
    else:
        conn.rollback()
        print("\n❌ Changes ROLLED BACK")
        
except Exception as e:
    conn.rollback()
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    raise
    
finally:
    cur.close()
    conn.close()
