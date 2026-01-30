"""
Find cheques 71 and 73
"""
import psycopg2
import pandas as pd

def main():
    print("=" * 80)
    print("SEARCHING FOR CHEQUES #71 AND #73")
    print("=" * 80)
    
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    
    try:
        # Search for cheques ending in 71 and 73
        query = """
            SELECT 
                receipt_id,
                receipt_date,
                vendor_name,
                description,
                gross_amount,
                net_amount,
                gst_amount,
                category,
                payment_method,
                mapped_bank_account_id,
                banking_transaction_id
            FROM receipts
            WHERE description ILIKE '%71%'
            OR description ILIKE '%73%'
            ORDER BY receipt_date DESC
        """
        
        df = pd.read_sql_query(query, conn)
        print(f"\nTotal records with '71' or '73': {len(df):,}\n")
        
        # More specific search for CHQ 71 and CHQ 73
        print("=" * 80)
        print("SEARCHING FOR 'CHQ 71' AND 'CHQ 73' (EXACT)")
        print("=" * 80)
        
        for chq_num in ['71', '73']:
            query_specific = f"""
                SELECT 
                    receipt_id,
                    receipt_date,
                    vendor_name,
                    description,
                    gross_amount,
                    category,
                    payment_method
                FROM receipts
                WHERE (description ILIKE '%CHQ%71%' 
                   OR description ILIKE '%CHQ 71%'
                   OR description ILIKE '%CHEQUE 71%'
                   OR description ILIKE '%CHECK 71%')
                AND payment_method ILIKE '%cheque%'
                ORDER BY receipt_date
            """
            
            if chq_num == '73':
                query_specific = query_specific.replace('%71%', '%73%')
            
            result = pd.read_sql_query(query_specific, conn)
            
            print(f"\nCHEQUE #{chq_num}:")
            print(f"  Found: {len(result)} record(s)")
            
            if len(result) > 0:
                print("\nDetails:")
                for idx, row in result.iterrows():
                    print(f"  Receipt ID: {row['receipt_id']}")
                    print(f"  Date: {row['receipt_date']}")
                    print(f"  Vendor: {row['vendor_name']}")
                    print(f"  Description: {row['description']}")
                    print(f"  Amount: ${row['gross_amount']:,.2f}")
                    print(f"  Category: {row['category']}")
                    print()
            else:
                print("  No records found")
        
        # Also search in banking transactions
        print("=" * 80)
        print("SEARCHING IN BANKING TRANSACTIONS")
        print("=" * 80)
        
        for chq_num in ['71', '73']:
            query_banking = f"""
                SELECT 
                    transaction_id,
                    transaction_date,
                    description,
                    debit_amount,
                    credit_amount,
                    vendor_extracted,
                    account_number
                FROM banking_transactions
                WHERE description ILIKE '%{chq_num}%'
                ORDER BY transaction_date
            """
            
            result = pd.read_sql_query(query_banking, conn)
            
            print(f"\nBANKING - CHQ #{chq_num}:")
            print(f"  Found: {len(result)} record(s)")
            
            if len(result) > 0:
                print("\nDetails:")
                for idx, row in result.iterrows():
                    print(f"  Transaction ID: {row['transaction_id']}")
                    print(f"  Date: {row['transaction_date']}")
                    print(f"  Description: {row['description']}")
                    print(f"  Amount: ${(row['debit_amount'] or row['credit_amount']):,.2f}")
                    print(f"  Account: {row['account_number']}")
                    print()
        
        print("✅ SEARCH COMPLETE")
        
    finally:
        conn.close()

if __name__ == '__main__':
    main()
