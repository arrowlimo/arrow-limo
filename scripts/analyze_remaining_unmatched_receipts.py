#!/usr/bin/env python3
"""
Analyze the remaining unmatched receipts to understand why they didn't match.
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("ANALYSIS OF REMAINING UNMATCHED RECEIPTS")
    print("="*80)
    
    # Get unmatched receipts
    cur.execute("""
        SELECT 
            r.receipt_id,
            r.receipt_date,
            r.vendor_name,
            r.gross_amount,
            r.category,
            r.description
        FROM receipts r
        WHERE r.business_personal = 'Business'
        AND NOT EXISTS (
            SELECT 1 FROM banking_receipt_matching_ledger bm
            WHERE bm.receipt_id = r.receipt_id
        )
        ORDER BY r.gross_amount DESC
        LIMIT 50
    """)
    
    unmatched = cur.fetchall()
    
    print(f"\nTop 50 unmatched receipts by amount:")
    print(f"{'ID':>10} {'Date':>12} {'Amount':>12} {'Vendor':>30} {'Category':>20}")
    print(f"{'-'*10} {'-'*12} {'-'*12} {'-'*30} {'-'*20}")
    
    total_shown = 0
    for receipt in unmatched:
        rid, rdate, vendor, amount, category, desc = receipt
        vendor_display = (vendor or 'Unknown')[:30]
        category_display = (category or 'None')[:20]
        total_shown += float(amount)
        print(f"{rid:10} {str(rdate):12} ${float(amount):>10.2f} {vendor_display:30} {category_display:20}")
    
    print(f"\nTotal of top 50: ${total_shown:,.2f}")
    
    # Check if these have any banking transactions on same date
    print("\n" + "="*80)
    print("Checking for potential banking matches on same dates...")
    print("="*80)
    
    for receipt in unmatched[:10]:  # Check first 10
        rid, rdate, vendor, amount, category, desc = receipt
        
        print(f"\nReceipt {rid}: {rdate} | {vendor} | ${amount:.2f}")
        
        # Look for banking transactions on same date
        cur.execute("""
            SELECT 
                transaction_id,
                description,
                debit_amount,
                credit_amount,
                account_number
            FROM banking_transactions
            WHERE transaction_date = %s
            AND account_number IN ('0228362', '3714081')
            AND (debit_amount IS NOT NULL OR credit_amount IS NOT NULL)
            ORDER BY ABS(COALESCE(debit_amount, credit_amount) - %s)
            LIMIT 3
        """, (rdate, amount))
        
        banking = cur.fetchall()
        
        if banking:
            print("  Possible banking matches on same date:")
            for bt in banking:
                bt_id, bt_desc, bt_debit, bt_credit, bt_acct = bt
                bt_amt = bt_debit if bt_debit else bt_credit
                acct_name = 'CIBC' if bt_acct == '0228362' else 'Scotia'
                print(f"    {acct_name} TX{bt_id}: ${bt_amt:.2f} - {bt_desc[:60]}")
        else:
            print("  No banking transactions found on this date")
    
    # Check date range of unmatched vs banking
    print("\n" + "="*80)
    print("Date range analysis...")
    print("="*80)
    
    cur.execute("""
        SELECT 
            MIN(receipt_date) as earliest_receipt,
            MAX(receipt_date) as latest_receipt,
            COUNT(*) as total_unmatched
        FROM receipts r
        WHERE r.business_personal = 'Business'
        AND NOT EXISTS (
            SELECT 1 FROM banking_receipt_matching_ledger bm
            WHERE bm.receipt_id = r.receipt_id
        )
    """)
    
    receipt_range = cur.fetchone()
    print(f"\nUnmatched receipts date range: {receipt_range[0]} to {receipt_range[1]}")
    print(f"Total unmatched: {receipt_range[2]}")
    
    cur.execute("""
        SELECT 
            MIN(transaction_date) as earliest,
            MAX(transaction_date) as latest,
            COUNT(*) as total_transactions
        FROM banking_transactions
        WHERE account_number IN ('0228362', '3714081')
    """)
    
    banking_range = cur.fetchone()
    print(f"\nBanking transactions date range: {banking_range[0]} to {banking_range[1]}")
    print(f"Total banking transactions: {banking_range[2]}")
    
    # Check for receipts outside banking date range
    cur.execute("""
        SELECT COUNT(*), ROUND(SUM(gross_amount)::numeric, 2)
        FROM receipts r
        WHERE r.business_personal = 'Business'
        AND NOT EXISTS (
            SELECT 1 FROM banking_receipt_matching_ledger bm
            WHERE bm.receipt_id = r.receipt_id
        )
        AND (r.receipt_date < %s OR r.receipt_date > %s)
    """, (banking_range[0], banking_range[1]))
    
    outside_range = cur.fetchone()
    print(f"\nReceipts OUTSIDE banking date range: {outside_range[0]} (${outside_range[1]:,.2f})")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
