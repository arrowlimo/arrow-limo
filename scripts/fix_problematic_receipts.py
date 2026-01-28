#!/usr/bin/env python3
"""
Fix the problematic issues found:
1. Receipt 58390 - INFINITE INNOVATIONS failed extraction
2. 5 large withdrawals NOT in banking (likely duplicates/bogus)
3. TD INSURANCE monthly payment receipt (should be monthly payments, not summary)
"""

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("FIXING PROBLEMATIC RECEIPTS")
    print("=" * 80)
    
    # Fix 1: Receipt 58390 - Manual fix for INFINITE INNOVATIONS
    print("\n1. Fixing Receipt 58390 - INFINITE INNOVATIONS extraction failure")
    cur.execute("""
        UPDATE receipts
        SET vendor_name = 'INFINITE INNOVATIONS (USD)',
            description = '$891.37 @ 1.347'
        WHERE receipt_id = 58390
    """)
    print(f"✅ Fixed Receipt 58390: INFINITE INNOVATIONS (USD) $891.37 @ 1.347")
    
    # Fix 2: Identify the 5 large withdrawals NOT in banking
    print("\n2. Investigating 5 large withdrawals NOT in banking...")
    cur.execute("""
        SELECT 
            r.receipt_id,
            r.receipt_date,
            r.vendor_name,
            r.gross_amount,
            r.description,
            r.payment_method,
            r.category
        FROM receipts r
        LEFT JOIN banking_receipt_matching_ledger brml ON r.receipt_id = brml.receipt_id
        WHERE brml.receipt_id IS NULL
          AND (r.description LIKE '%withdrawal%'
           OR r.description LIKE '%withdraw%'
           OR r.vendor_name LIKE '%WITHDRAWAL%'
           OR r.vendor_name LIKE '%ATM%'
           OR r.vendor_name LIKE '%CASH%')
          AND r.gross_amount > 1000
        ORDER BY r.gross_amount DESC
    """)
    
    unmatched_withdrawals = cur.fetchall()
    print(f"Found {len(unmatched_withdrawals)} large withdrawals NOT in banking:")
    
    for receipt_id, date, vendor, amount, desc, payment, category in unmatched_withdrawals:
        print(f"\n  Receipt {receipt_id}:")
        print(f"    Date: {date}")
        print(f"    Vendor: {vendor}")
        print(f"    Amount: ${amount:,.2f}")
        print(f"    Payment: {payment}")
        print(f"    Category: {category}")
        print(f"    Description: {desc}")
        
        # Check if there's a matching banking transaction by date+amount
        cur.execute("""
            SELECT 
                bt.transaction_id,
                bt.transaction_date,
                bt.description,
                bt.debit_amount,
                CASE WHEN brml.banking_transaction_id IS NOT NULL THEN 'MATCHED' ELSE 'UNMATCHED' END as status
            FROM banking_transactions bt
            LEFT JOIN banking_receipt_matching_ledger brml ON bt.transaction_id = brml.banking_transaction_id
            WHERE bt.transaction_date = %s
              AND ABS(bt.debit_amount - %s) < 0.01
        """, (date, amount))
        
        matching_banking = cur.fetchall()
        if matching_banking:
            print(f"    ⚠️  FOUND MATCHING BANKING:")
            for tx_id, tx_date, tx_desc, tx_amt, status in matching_banking:
                print(f"      TX {tx_id} | {tx_date} | ${tx_amt:,.2f} | {status}")
                print(f"        {tx_desc[:70]}")
        else:
            print(f"    ❌ NO MATCHING BANKING FOUND - Likely BOGUS/DUPLICATE")
    
    # Fix 3: Check TD INSURANCE monthly summary
    print("\n\n3. Checking TD INSURANCE monthly summary receipt...")
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            description,
            payment_method,
            category
        FROM receipts
        WHERE description LIKE '%12 monthly%'
    """)
    
    td_summary = cur.fetchall()
    if td_summary:
        for receipt_id, date, vendor, amount, desc, payment, category in td_summary:
            print(f"  Receipt {receipt_id}:")
            print(f"    Date: {date}")
            print(f"    Vendor: {vendor}")
            print(f"    Amount: ${amount:,.2f}")
            print(f"    Description: {desc}")
            print(f"    Payment: {payment}")
            
            # Check if there are 12 individual monthly payments
            cur.execute("""
                SELECT COUNT(*), SUM(gross_amount)
                FROM receipts
                WHERE vendor_name LIKE '%TD INSURANCE%'
                  AND receipt_date >= %s
                  AND receipt_date <= %s::date + INTERVAL '12 months'
                  AND receipt_id != %s
            """, (date, date, receipt_id))
            
            count, total = cur.fetchone()
            print(f"    Found {count} other TD INSURANCE receipts in 12-month period: ${total or 0:,.2f}")
            
            if count >= 11:
                print(f"    ✅ There ARE individual monthly payments - this summary is DUPLICATE")
                print(f"    RECOMMENDATION: Delete receipt {receipt_id}")
            else:
                print(f"    ⚠️  Missing individual monthly payments - this summary may be legitimate")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY AND RECOMMENDATIONS")
    print("=" * 80)
    
    print("\n1. USD tracking: Fixed Receipt 58390 INFINITE INNOVATIONS")
    print("\n2. Large withdrawals NOT in banking:")
    print("   → Check each one above for matching banking transactions")
    print("   → If no match found, likely duplicate/bogus - recommend deletion")
    
    print("\n3. TD INSURANCE summary:")
    print("   → If individual monthly payments exist, delete summary receipt")
    print("   → If not, keep summary and investigate why monthly payments are missing")
    
    conn.commit()
    print(f"\n✅ All fixes committed to database")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
