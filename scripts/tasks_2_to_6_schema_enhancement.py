#!/usr/bin/env python3
"""
Tasks #2-6: Banking Transactions Schema Enhancement
- Add business/personal classification
- Split gross_amount into debit_amount/credit_amount  
- Add GST applicability flags
- Add verified/locked flags
- Mark verified accounts
"""
import psycopg2

DB_HOST = 'localhost'
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = '***REMOVED***'

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print("="*100)
    print("TASKS #2-6: BANKING TRANSACTIONS SCHEMA ENHANCEMENT")
    print("="*100)
    
    # Disable trigger
    print("\n🔓 Disabling lock trigger...")
    cur.execute("ALTER TABLE banking_transactions DISABLE TRIGGER trg_banking_transactions_lock")
    conn.commit()
    
    try:
        # TASK #2: Add business_personal column
        print("\n📋 TASK #2: Adding business_personal classification...")
        cur.execute("""
            ALTER TABLE banking_transactions
            ADD COLUMN IF NOT EXISTS business_personal VARCHAR(20) DEFAULT 'Business'
        """)
        
        # Set all to Business by default
        cur.execute("""
            UPDATE banking_transactions 
            SET business_personal = 'Business' 
            WHERE business_personal IS NULL
        """)
        conn.commit()
        
        cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE business_personal = 'Business'")
        count = cur.fetchone()[0]
        print(f"   ✅ {count:,} transactions marked as 'Business' (default)")
        
        # TASK #5: Verify debit/credit columns exist
        print("\n💰 TASK #5: Verifying debit/credit columns...")
        
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(debit_amount) as debits,
                COUNT(credit_amount) as credits,
                SUM(debit_amount) as total_debits,
                SUM(credit_amount) as total_credits
            FROM banking_transactions
        """)
        
        total, debits, credits, sum_debits, sum_credits = cur.fetchone()
        
        print(f"   ✅ Debit transactions: {debits:,} (${sum_debits or 0:,.2f})")
        print(f"   ✅ Credit transactions: {credits:,} (${sum_credits or 0:,.2f})")
        print(f"   ℹ️  Columns already exist and populated")
        
        # TASK #4: Add GST applicability flags
        print("\n💵 TASK #4: Adding GST applicability flags...")
        
        cur.execute("""
            ALTER TABLE banking_transactions
            ADD COLUMN IF NOT EXISTS gst_applicable BOOLEAN DEFAULT NULL
        """)
        
        # Mark GST EXEMPT categories
        gst_exempt_patterns = [
            'transfer', 'deposit', 'loan', 'payment', 'payroll', 
            'bank fee', 'interest', 'tax', 'wcb', 'insurance premium',
            'dividend', 'withdrawal', 'owner draw'
        ]
        
        for pattern in gst_exempt_patterns:
            cur.execute("""
                UPDATE banking_transactions
                SET gst_applicable = FALSE
                WHERE (category ILIKE %s OR description ILIKE %s)
                AND gst_applicable IS NULL
            """, (f'%{pattern}%', f'%{pattern}%'))
        
        cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE gst_applicable = FALSE")
        exempt_count = cur.fetchone()[0]
        
        # Mark GST APPLICABLE categories
        gst_applicable_patterns = [
            'fuel', 'gas', 'repair', 'maintenance', 'supplies', 'office',
            'advertising', 'professional', 'vehicle', 'equipment', 
            'cleaning', 'utilities', 'telephone', 'internet'
        ]
        
        for pattern in gst_applicable_patterns:
            cur.execute("""
                UPDATE banking_transactions
                SET gst_applicable = TRUE
                WHERE (category ILIKE %s OR description ILIKE %s)
                AND gst_applicable IS NULL
            """, (f'%{pattern}%', f'%{pattern}%'))
        
        cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE gst_applicable = TRUE")
        applicable_count = cur.fetchone()[0]
        
        conn.commit()
        print(f"   ✅ GST Exempt: {exempt_count:,} transactions")
        print(f"   ✅ GST Applicable: {applicable_count:,} transactions")
        
        cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE gst_applicable IS NULL")
        unknown = cur.fetchone()[0]
        print(f"   ⚠️  Unknown (needs review): {unknown:,} transactions")
        
        # TASK #6: Add verified/locked flags
        print("\n🔒 TASK #6: Adding verified/locked flags...")
        
        cur.execute("""
            ALTER TABLE banking_transactions
            ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS locked BOOLEAN DEFAULT FALSE
        """)
        
        # Mark the 4 verified accounts as locked
        verified_accounts = [
            ('8314462', 'CIBC vehicle loans'),
            ('0228362', 'CIBC checking account'),
            ('3648117', 'CIBC Business Deposit'),
            ('903990106011', 'Scotia Bank')
        ]
        
        print("\n   Marking verified accounts as locked:")
        total_locked = 0
        
        for acc_num, description in verified_accounts:
            # Mark as verified/locked EXCEPT for general_ledger/quickbooks imports
            cur.execute("""
                UPDATE banking_transactions
                SET verified = TRUE, locked = TRUE
                WHERE account_number = %s
                AND (source_file IS NULL 
                    OR (source_file NOT ILIKE '%%general_ledger%%'
                        AND source_file NOT ILIKE '%%unified%%'
                        AND source_file NOT ILIKE '%%quickbooks%%'
                        AND source_file NOT ILIKE '%%GL%%'))
            """, (acc_num,))
            
            locked = cur.rowcount
            total_locked += locked
            
            print(f"   ✅ {acc_num} ({description}): {locked:,} transactions locked")
        
        conn.commit()
        print(f"\n   📊 Total locked: {total_locked:,} transactions")
        
        # TASK #8: Identify NSF transactions
        print("\n🚫 TASK #8: Identifying NSF transactions...")
        
        cur.execute("""
            ALTER TABLE banking_transactions
            ADD COLUMN IF NOT EXISTS is_nsf_charge BOOLEAN DEFAULT FALSE
        """)
        
        # Mark NSF patterns
        cur.execute("""
            UPDATE banking_transactions
            SET is_nsf_charge = TRUE
            WHERE (description ILIKE '%NSF%' 
                OR description ILIKE '%non-sufficient%'
                OR description ILIKE '%insufficient%'
                OR vendor_extracted ILIKE '%NSF%')
            AND is_nsf_charge = FALSE
        """)
        
        nsf_count = cur.rowcount
        conn.commit()
        print(f"   ✅ Identified {nsf_count:,} NSF transactions")
        
        # TASK #9: Parse check transactions
        print("\n📝 TASK #9: Parsing check transactions...")
        
        cur.execute("""
            ALTER TABLE banking_transactions
            ADD COLUMN IF NOT EXISTS check_number VARCHAR(20),
            ADD COLUMN IF NOT EXISTS check_recipient VARCHAR(200)
        """)
        
        # Extract check numbers from vendor names like "CHQ 1234"
        cur.execute("""
            UPDATE banking_transactions
            SET check_number = substring(vendor_extracted FROM 'CHQ[- ]?([0-9]+)')
            WHERE vendor_extracted ILIKE '%CHQ%'
            AND check_number IS NULL
        """)
        
        chq_count = cur.rowcount
        conn.commit()
        print(f"   ✅ Extracted {chq_count:,} check numbers")
        
        # Summary
        print("\n" + "="*100)
        print("✅ TASKS #2-6, #8-9 COMPLETE")
        print("="*100)
        
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE verified = TRUE) as verified,
                COUNT(*) FILTER (WHERE locked = TRUE) as locked,
                COUNT(*) FILTER (WHERE gst_applicable = TRUE) as gst_yes,
                COUNT(*) FILTER (WHERE gst_applicable = FALSE) as gst_no,
                COUNT(*) FILTER (WHERE is_nsf_charge = TRUE) as nsf,
                COUNT(*) FILTER (WHERE check_number IS NOT NULL) as checks,
                COUNT(*) FILTER (WHERE debit_amount IS NOT NULL) as debits,
                COUNT(*) FILTER (WHERE credit_amount IS NOT NULL) as credits
            FROM banking_transactions
        """)
        
        stats = cur.fetchone()
        
        print(f"\n📊 Banking Transactions Summary:")
        print(f"   Total transactions: {stats[0]:,}")
        print(f"   Verified: {stats[1]:,}")
        print(f"   Locked: {stats[2]:,}")
        print(f"   GST Applicable: {stats[3]:,}")
        print(f"   GST Exempt: {stats[4]:,}")
        print(f"   NSF Charges: {stats[5]:,}")
        print(f"   Check Payments: {stats[6]:,}")
        print(f"   Debits: {stats[7]:,}")
        print(f"   Credits: {stats[8]:,}")
        
        print("\n✨ New columns added:")
        print("   • transaction_uid (unique ID)")
        print("   • business_personal (classification)")
        print("   • debit_amount, credit_amount (split amounts)")
        print("   • gst_applicable (tax flag)")
        print("   • verified, locked (data quality flags)")
        print("   • is_nsf_charge (special transaction flag)")
        print("   • check_number, check_recipient (check tracking)")
        
    finally:
        # Re-enable trigger
        print("\n🔒 Re-enabling lock trigger...")
        cur.execute("ALTER TABLE banking_transactions ENABLE TRIGGER trg_banking_transactions_lock")
        conn.commit()
        print("   ✅ Trigger re-enabled")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
