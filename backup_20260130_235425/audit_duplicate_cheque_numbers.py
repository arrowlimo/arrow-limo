#!/usr/bin/env python3
"""
Audit cheque numbers - find duplicates with different amounts
QuickBooks often has bogus entries with same cheque number but different amounts
"""
import psycopg2
import pandas as pd
from datetime import datetime

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
    
    print("="*100)
    print("CHEQUE NUMBER AUDIT - Finding Duplicate Cheques with Different Amounts")
    print("="*100)
    
    # Check banking_transactions for cheques
    print("\n" + "="*100)
    print("BANKING TRANSACTIONS - DUPLICATE CHEQUE NUMBERS")
    print("="*100)
    
    cur.execute("""
        SELECT 
            check_number,
            COUNT(*) as transaction_count,
            COUNT(DISTINCT debit_amount) as distinct_debit_amounts,
            COUNT(DISTINCT credit_amount) as distinct_credit_amounts,
            ARRAY_AGG(DISTINCT debit_amount ORDER BY debit_amount) FILTER (WHERE debit_amount IS NOT NULL) as debit_amounts,
            ARRAY_AGG(DISTINCT credit_amount ORDER BY credit_amount) FILTER (WHERE credit_amount IS NOT NULL) as credit_amounts,
            ARRAY_AGG(transaction_id ORDER BY transaction_date) as transaction_ids,
            ARRAY_AGG(transaction_date ORDER BY transaction_date) as dates,
            ARRAY_AGG(description ORDER BY transaction_date) as descriptions,
            ARRAY_AGG(account_number ORDER BY transaction_date) as accounts
        FROM banking_transactions
        WHERE check_number IS NOT NULL 
        AND check_number != ''
        GROUP BY check_number
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC, check_number
    """)
    
    banking_dupes = cur.fetchall()
    
    print(f"\nFound {len(banking_dupes)} cheque numbers with multiple banking transactions")
    
    # Analyze banking duplicates
    same_amount = []
    different_amounts = []
    
    for row in banking_dupes:
        chq_num, count, distinct_debit, distinct_credit, debits, credits, tx_ids, dates, descs, accounts = row
        
        # Check if amounts vary
        total_distinct = (distinct_debit if distinct_debit else 0) + (distinct_credit if distinct_credit else 0)
        
        if total_distinct > 1:
            different_amounts.append(row)
        else:
            same_amount.append(row)
    
    print(f"\nSame amount (likely legitimate recurring): {len(same_amount)}")
    print(f"DIFFERENT amounts (SUSPICIOUS - likely bogus): {len(different_amounts)}")
    
    if different_amounts:
        print(f"\n{'='*100}")
        print("SUSPICIOUS DUPLICATE CHEQUES (Different Amounts) - TOP 30")
        print(f"{'='*100}")
        
        for row in different_amounts[:30]:
            chq_num, count, distinct_debit, distinct_credit, debits, credits, tx_ids, dates, descs, accounts = row
            
            print(f"\n🚨 CHEQUE #{chq_num} - {count} transactions with DIFFERENT amounts")
            
            # Show all transactions
            for i, (tx_id, date, desc, acct) in enumerate(zip(tx_ids, dates, descs, accounts), 1):
                # Get amount for this specific transaction
                cur.execute("""
                    SELECT debit_amount, credit_amount, balance
                    FROM banking_transactions
                    WHERE transaction_id = %s
                """, (tx_id,))
                
                tx_data = cur.fetchone()
                if tx_data:
                    debit, credit, balance = tx_data
                    amount = debit if debit else credit
                    amt_type = "DEBIT" if debit else "CREDIT"
                    
                    account_name = "CIBC 0228362" if "0228362" in str(acct) else "Scotia 903990106011" if "903990106011" in str(acct) else acct
                    
                    print(f"  {i}. TX #{tx_id} | {date} | ${amount:.2f} ({amt_type}) | {account_name}")
                    print(f"     {desc}")
    
    # Check receipts for cheque payment method duplicates
    print(f"\n{'='*100}")
    print("RECEIPTS - DUPLICATE CHEQUE NUMBERS (payment_method = 'CHEQUE')")
    print(f"{'='*100}")
    
    # First check what payment methods indicate cheques
    cur.execute("""
        SELECT DISTINCT payment_method, pay_method, canonical_pay_method
        FROM receipts
        WHERE (payment_method ILIKE '%cheque%' OR payment_method ILIKE '%check%'
            OR pay_method ILIKE '%cheque%' OR pay_method ILIKE '%check%'
            OR canonical_pay_method ILIKE '%cheque%' OR canonical_pay_method ILIKE '%check%')
        AND payment_method IS NOT NULL
        LIMIT 20
    """)
    
    print("\nPayment methods that indicate cheques:")
    for row in cur.fetchall():
        print(f"  {row}")
    
    # Look for cheque numbers in description or vendor fields that might be duplicated
    cur.execute("""
        SELECT 
            SUBSTRING(description FROM 'CH(?:EQUE|Q|ECK)\\s*#?\\s*(\\d+)') as cheque_num,
            COUNT(*) as count,
            COUNT(DISTINCT gross_amount) as distinct_amounts,
            ARRAY_AGG(DISTINCT gross_amount ORDER BY gross_amount) as amounts,
            ARRAY_AGG(receipt_id ORDER BY receipt_date) as receipt_ids,
            ARRAY_AGG(receipt_date ORDER BY receipt_date) as dates,
            ARRAY_AGG(vendor_name ORDER BY receipt_date) as vendors
        FROM receipts
        WHERE description ~* 'CH(?:EQUE|Q|ECK)\\s*#?\\s*\\d+'
        GROUP BY SUBSTRING(description FROM 'CH(?:EQUE|Q|ECK)\\s*#?\\s*(\\d+)')
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
        LIMIT 50
    """)
    
    receipt_dupes = cur.fetchall()
    
    if receipt_dupes:
        print(f"\n{'='*100}")
        print(f"RECEIPTS WITH DUPLICATE CHEQUE NUMBERS (from description) - {len(receipt_dupes)} cases")
        print(f"{'='*100}")
        
        for row in receipt_dupes:
            chq_num, count, distinct_amts, amounts, rec_ids, dates, vendors = row
            
            if chq_num and distinct_amts > 1:  # Only show different amounts
                print(f"\n🚨 CHEQUE #{chq_num} in receipts - {count} entries with {distinct_amts} different amounts")
                print(f"   Amounts: {amounts}")
                for rec_id, date, vendor, amt in zip(rec_ids, dates, vendors, amounts):
                    print(f"   Receipt #{rec_id} | {date} | ${amt:.2f} | {vendor or 'NO VENDOR'}")
    
    # Export detailed report
    export_data = []
    
    for row in different_amounts:
        chq_num, count, distinct_debit, distinct_credit, debits, credits, tx_ids, dates, descs, accounts = row
        
        for tx_id, date, desc, acct in zip(tx_ids, dates, descs, accounts):
            cur.execute("""
                SELECT debit_amount, credit_amount, balance
                FROM banking_transactions
                WHERE transaction_id = %s
            """, (tx_id,))
            
            tx_data = cur.fetchone()
            if tx_data:
                debit, credit, balance = tx_data
                amount = debit if debit else credit
                
                export_data.append({
                    'cheque_number': chq_num,
                    'duplicate_count': count,
                    'transaction_id': tx_id,
                    'date': date,
                    'amount': amount,
                    'type': 'DEBIT' if debit else 'CREDIT',
                    'account': acct,
                    'description': desc,
                    'status': 'SUSPICIOUS_DUPLICATE'
                })
    
    if export_data:
        df = pd.DataFrame(export_data)
        output_file = f"l:/limo/reports/duplicate_cheques_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(output_file, index=False)
        print(f"\n{'='*100}")
        print(f"Detailed report exported to: {output_file}")
        print(f"{'='*100}")
    
    # Summary
    print(f"\n{'='*100}")
    print("SUMMARY")
    print(f"{'='*100}")
    print(f"\nBANKING TRANSACTIONS:")
    print(f"  Total duplicate cheque numbers: {len(banking_dupes)}")
    print(f"  Same amounts (legitimate): {len(same_amount)}")
    print(f"  DIFFERENT amounts (BOGUS): {len(different_amounts)}")
    
    if different_amounts:
        print(f"\n⚠️  ACTION REQUIRED:")
        print(f"  {len(different_amounts)} cheque numbers have multiple entries with different amounts")
        print(f"  These are likely QuickBooks import errors and should be reviewed")
        print(f"  Recommendation: Keep the transaction that matches actual bank statement,")
        print(f"                  delete or flag the bogus entries")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
