#!/usr/bin/env python3
"""
Re-analyze the large "maintenance" entries - check if amounts are data errors.
Look for patterns in cheque descriptions and actual amounts.
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
    print("RE-ANALYZING LARGE 'MAINTENANCE' ENTRIES")
    print("="*80)
    
    # Get all receipts with "Cheque" in vendor name and large amounts
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            description,
            gross_amount,
            gst_amount,
            net_amount
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
        AND gl_account_code = '5120'
        AND vendor_name ILIKE '%cheque%'
        AND gross_amount > 50000
        ORDER BY gross_amount DESC
    """)
    
    cheque_receipts = cur.fetchall()
    
    print(f"\nLarge 'Cheque' receipts in maintenance:")
    print("="*80)
    
    for receipt in cheque_receipts:
        receipt_id = receipt[0]
        date = receipt[1]
        vendor = receipt[2]
        description = receipt[3]
        amount = float(receipt[4])
        gst = float(receipt[5] or 0)
        net = float(receipt[6] or 0)
        
        # Calculate what the amount would be if decimal point was wrong
        corrected_amount = amount / 100
        corrected_gst = gst / 100
        
        print(f"\n{date} | Receipt ID: {receipt_id}")
        print(f"  Vendor: {vendor}")
        print(f"  Recorded Amount: ${amount:,.2f}")
        print(f"  IF DECIMAL ERROR: ${corrected_amount:,.2f} (divided by 100)")
        print(f"  GST recorded: ${gst:,.2f} → corrected: ${corrected_gst:,.2f}")
        print(f"  Description: {description}")
    
    # Now check what actual banking transactions show
    print(f"\n\n{'='*80}")
    print(f"WHAT BANKING ACTUALLY SHOWS")
    print(f"{'='*80}")
    
    dates_to_check = [
        '2012-10-31',
        '2012-07-13', 
        '2012-07-10',
        '2012-11-28',
        '2012-06-04'
    ]
    
    for date in dates_to_check:
        cur.execute("""
            SELECT 
                transaction_id,
                description,
                debit_amount,
                balance
            FROM banking_transactions
            WHERE transaction_date = %s
            AND account_number = '0228362'
            AND description ILIKE '%cheque%'
            ORDER BY debit_amount DESC
        """, (date,))
        
        banking = cur.fetchall()
        
        if banking:
            print(f"\n{date}:")
            for bank in banking:
                txn_id = bank[0]
                desc = bank[1]
                debit = float(bank[2] or 0)
                balance = float(bank[3] or 0)
                
                print(f"  ${debit:12,.2f} OUT - {desc}")
                print(f"  Balance after: ${balance:,.2f}")
    
    # Look for amounts around $1,954, $1,583, $1,363, $1,133
    print(f"\n\n{'='*80}")
    print(f"SEARCHING FOR SMALLER CHEQUE AMOUNTS (IF DECIMAL ERROR)")
    print(f"{'='*80}")
    
    search_amounts = [
        (1954.06, '2012-10-31'),
        (1583.63, '2012-07-13'),
        (1582.43, '2012-07-10'),
        (1362.87, '2012-11-28'),
        (1133.32, '2012-06-04')
    ]
    
    for search_amt, search_date in search_amounts:
        cur.execute("""
            SELECT 
                transaction_date,
                description,
                debit_amount,
                credit_amount
            FROM banking_transactions
            WHERE transaction_date BETWEEN %s::date - INTERVAL '5 days' 
                AND %s::date + INTERVAL '5 days'
            AND (ABS(debit_amount - %s) < 10 OR ABS(credit_amount - %s) < 10)
            ORDER BY transaction_date
        """, (search_date, search_date, search_amt, search_amt))
        
        results = cur.fetchall()
        
        if results:
            print(f"\nSearching for ~${search_amt:,.2f} near {search_date}:")
            for result in results:
                date = result[0]
                desc = result[1][:60]
                debit = float(result[2] or 0)
                credit = float(result[3] or 0)
                
                if debit > 0:
                    print(f"  {date}: ${debit:10,.2f} OUT - {desc}")
                else:
                    print(f"  {date}: ${credit:10,.2f} IN  - {desc}")
    
    # Check the actual balance patterns
    print(f"\n\n{'='*80}")
    print(f"BALANCE ANALYSIS - PROVING THE AMOUNTS")
    print(f"{'='*80}")
    
    cur.execute("""
        SELECT 
            transaction_date,
            description,
            debit_amount,
            balance,
            LAG(balance) OVER (ORDER BY transaction_date, transaction_id) as prev_balance
        FROM banking_transactions
        WHERE transaction_date IN ('2012-10-31', '2012-07-13', '2012-07-10', '2012-11-28', '2012-06-04')
        AND account_number = '0228362'
        AND debit_amount > 1000
        ORDER BY transaction_date, transaction_id
    """)
    
    balance_checks = cur.fetchall()
    
    print(f"\nBalance proof (if amount is correct, balance should match):")
    for check in balance_checks:
        date = check[0]
        desc = check[1][:50]
        debit = float(check[2] or 0)
        balance = float(check[3] or 0)
        prev_balance = float(check[4] or 0) if check[4] else 0
        
        calculated_balance = prev_balance - debit
        matches = abs(calculated_balance - balance) < 1
        
        print(f"\n{date}: ${debit:,.2f} OUT")
        print(f"  Previous: ${prev_balance:,.2f}")
        print(f"  Current:  ${balance:,.2f}")
        print(f"  Calculated: ${calculated_balance:,.2f}")
        print(f"  {'✓ MATCHES' if matches else '✗ DOES NOT MATCH'}")
        print(f"  {desc}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
