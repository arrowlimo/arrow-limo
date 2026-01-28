#!/usr/bin/env python3
"""
Get detailed information on the 5 largest cheque payments in 2012.
"""

import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("="*80)
    print("DETAILED ANALYSIS OF 5 LARGEST CHEQUE PAYMENTS (2012)")
    print("="*80)
    
    # List of the 5 largest cheques
    cheques = [
        ('2012-10-31', 195406.00, 'Cheque #-955.46'),
        ('2012-07-13', 158362.70, 'Cheque #WO -120.00'),
        ('2012-07-10', 158242.70, 'Cheque #DD Eries Auto Repair -1,024.28'),
        ('2012-11-28', 136287.00, 'Cheque #dd Princess Auto -78.74'),
        ('2012-06-04', 113332.00, 'Cheque #DD Warehouse One -128.59')
    ]
    
    for i, cheque_info in enumerate(cheques, 1):
        date = cheque_info[0]
        amount = cheque_info[1]
        description = cheque_info[2]
        
        print(f"\n{'='*80}")
        print(f"CHEQUE #{i}: ${amount:,.2f} on {date}")
        print(f"{'='*80}")
        
        # Find in banking_transactions
        cur.execute("""
            SELECT 
                transaction_id,
                account_number,
                description,
                debit_amount,
                credit_amount,
                balance
            FROM banking_transactions
            WHERE transaction_date = %s
            AND debit_amount = %s
            ORDER BY transaction_id
        """, (date, amount))
        
        banking = cur.fetchall()
        
        if banking:
            print(f"\nBANKING TRANSACTION(S):")
            for bank in banking:
                txn_id = bank[0]
                account = bank[1]
                desc = bank[2]
                debit = float(bank[3] or 0)
                credit = float(bank[4] or 0)
                balance = float(bank[5] or 0)
                
                print(f"\n  Transaction ID: {txn_id}")
                print(f"  Account: {account}")
                print(f"  Description: {desc}")
                print(f"  Debit (out): ${debit:,.2f}")
                print(f"  Balance after: ${balance:,.2f}")
        
        # Find related receipts
        cur.execute("""
            SELECT 
                receipt_id,
                vendor_name,
                description,
                gross_amount,
                gst_amount,
                net_amount,
                gl_account_code,
                category
            FROM receipts
            WHERE receipt_date = %s
            AND gross_amount = %s
            ORDER BY receipt_id
        """, (date, amount))
        
        receipts = cur.fetchall()
        
        if receipts:
            print(f"\n  RECEIPT(S) LINKED:")
            for receipt in receipts:
                receipt_id = receipt[0]
                vendor = receipt[1] or 'Unknown'
                desc = receipt[2] or 'N/A'
                gross = float(receipt[3])
                gst = float(receipt[4] or 0)
                net = float(receipt[5] or 0)
                gl_code = receipt[6] or 'N/A'
                category = receipt[7] or 'N/A'
                
                print(f"\n    Receipt ID: {receipt_id}")
                print(f"    Vendor: {vendor}")
                print(f"    Description: {desc}")
                print(f"    Gross: ${gross:,.2f} | GST: ${gst:,.2f} | Net: ${net:,.2f}")
                print(f"    GL Code: {gl_code} | Category: {category}")
        
        # Check if linked via banking_receipt_matching_ledger
        if banking:
            for bank in banking:
                txn_id = bank[0]
                
                cur.execute("""
                    SELECT 
                        bm.receipt_id,
                        bm.match_type,
                        bm.match_confidence,
                        bm.notes,
                        r.vendor_name,
                        r.gross_amount,
                        r.gl_account_code
                    FROM banking_receipt_matching_ledger bm
                    JOIN receipts r ON r.receipt_id = bm.receipt_id
                    WHERE bm.banking_transaction_id = %s
                """, (txn_id,))
                
                matches = cur.fetchall()
                
                if matches:
                    print(f"\n  BANKING LINKAGE:")
                    for match in matches:
                        match_receipt_id = match[0]
                        match_type = match[1]
                        confidence = match[2]
                        notes = match[3] or 'N/A'
                        match_vendor = match[4] or 'Unknown'
                        match_amount = float(match[5])
                        match_gl = match[6] or 'N/A'
                        
                        print(f"    → Linked to Receipt #{match_receipt_id}")
                        print(f"       Vendor: {match_vendor}")
                        print(f"       Amount: ${match_amount:,.2f}")
                        print(f"       GL Code: {match_gl}")
                        print(f"       Match Type: {match_type} ({confidence}% confidence)")
        
        # Look for related transactions around the same date (±7 days)
        print(f"\n  RELATED TRANSACTIONS (±7 days):")
        
        cur.execute("""
            SELECT 
                transaction_date,
                description,
                debit_amount,
                credit_amount,
                balance
            FROM banking_transactions
            WHERE transaction_date BETWEEN %s::date - INTERVAL '7 days' 
                AND %s::date + INTERVAL '7 days'
            AND account_number = '0228362'
            AND (debit_amount > 1000 OR credit_amount > 1000)
            AND transaction_date != %s
            ORDER BY transaction_date, debit_amount DESC
            LIMIT 10
        """, (date, date, date))
        
        related = cur.fetchall()
        
        if related:
            for rel in related:
                rel_date = rel[0]
                rel_desc = rel[1][:60]
                rel_debit = float(rel[2] or 0)
                rel_credit = float(rel[3] or 0)
                rel_balance = float(rel[4] or 0)
                
                if rel_debit > 0:
                    print(f"    {rel_date}: ${rel_debit:10,.2f} OUT - {rel_desc}")
                else:
                    print(f"    {rel_date}: ${rel_credit:10,.2f} IN  - {rel_desc}")
    
    # Summary analysis
    print(f"\n\n{'='*80}")
    print(f"SUMMARY ANALYSIS")
    print(f"{'='*80}")
    
    total = sum(c[1] for c in cheques)
    print(f"\nTotal of 5 cheques: ${total:,.2f}")
    
    # Check what was purchased
    cur.execute("""
        SELECT DISTINCT
            vendor_name,
            COUNT(*) as receipt_count,
            SUM(gross_amount) as total_amount
        FROM receipts
        WHERE receipt_date IN ('2012-10-31', '2012-07-13', '2012-07-10', '2012-11-28', '2012-06-04')
        AND gross_amount > 100000
        GROUP BY vendor_name
        ORDER BY total_amount DESC
    """)
    
    vendors = cur.fetchall()
    
    if vendors:
        print(f"\n\nVendors receiving large payments on these dates:")
        for vendor_data in vendors:
            vendor = vendor_data[0] or 'Unknown'
            count = vendor_data[1]
            amount = float(vendor_data[2])
            print(f"  • {vendor[:50]:50s} | {count} receipts | ${amount:,.2f}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
