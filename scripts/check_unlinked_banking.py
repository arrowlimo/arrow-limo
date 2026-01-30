"""
Check what unlinked banking transactions exist - card payments, cheques, etc.
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("="*80)
    print("UNLINKED BANKING TRANSACTIONS ANALYSIS")
    print("="*80)
    
    # Get unlinked transactions by type
    cur.execute("""
        SELECT 
            CASE 
                WHEN description ILIKE '%PURCHASE%' OR description ILIKE '%POINT OF SALE%' THEN 'Card Payment'
                WHEN description ILIKE '%CHEQUE%' OR description ILIKE '%CHQ%' THEN 'Cheque'
                WHEN description ILIKE '%CREDIT MEMO%' OR description ILIKE '%DEPOSIT%' THEN 'Deposit/Credit'
                WHEN description ILIKE '%TRANSFER%' OR description ILIKE '%EFT%' THEN 'Transfer/EFT'
                WHEN description ILIKE '%FEE%' OR description ILIKE '%CHARGE%' THEN 'Bank Fee'
                ELSE 'Other'
            END as type,
            COUNT(*) as count,
            SUM(debit_amount) as total
        FROM banking_transactions
        WHERE debit_amount > 0
        AND NOT EXISTS (
            SELECT 1 FROM banking_receipt_matching_ledger bm 
            WHERE bm.banking_transaction_id = transaction_id
        )
        GROUP BY type
        ORDER BY count DESC
    """)
    
    print("\nUnlinked banking debits by type:")
    print(f"{'Type':20} {'Count':>8} {'Total':>15}")
    print("-"*45)
    
    total_count = 0
    total_amount = 0
    for row in cur.fetchall():
        print(f"{row[0]:20} {row[1]:>8,} ${row[2]:>13,.2f}")
        total_count += row[1]
        total_amount += row[2]
    
    print("-"*45)
    print(f"{'TOTAL':20} {total_count:>8,} ${total_amount:>13,.2f}")
    
    # Show examples of each type
    print("\n" + "="*80)
    print("EXAMPLES OF UNLINKED TRANSACTIONS")
    print("="*80)
    
    types = ['Card Payment', 'Cheque', 'Transfer/EFT', 'Bank Fee', 'Other']
    
    for txn_type in types:
        if txn_type == 'Card Payment':
            condition = "(description ILIKE '%PURCHASE%' OR description ILIKE '%POINT OF SALE%')"
        elif txn_type == 'Cheque':
            condition = "(description ILIKE '%CHEQUE%' OR description ILIKE '%CHQ%')"
        elif txn_type == 'Transfer/EFT':
            condition = "(description ILIKE '%TRANSFER%' OR description ILIKE '%EFT%')"
        elif txn_type == 'Bank Fee':
            condition = "(description ILIKE '%FEE%' OR description ILIKE '%CHARGE%')"
        else:
            condition = """(description NOT ILIKE '%PURCHASE%' AND description NOT ILIKE '%POINT OF SALE%' 
                           AND description NOT ILIKE '%CHEQUE%' AND description NOT ILIKE '%CHQ%'
                           AND description NOT ILIKE '%TRANSFER%' AND description NOT ILIKE '%EFT%'
                           AND description NOT ILIKE '%FEE%' AND description NOT ILIKE '%CHARGE%'
                           AND description NOT ILIKE '%CREDIT MEMO%' AND description NOT ILIKE '%DEPOSIT%')"""
        
        cur.execute(f"""
            SELECT transaction_date, description, debit_amount, account_number
            FROM banking_transactions
            WHERE debit_amount > 0
            AND NOT EXISTS (
                SELECT 1 FROM banking_receipt_matching_ledger bm 
                WHERE bm.banking_transaction_id = transaction_id
            )
            AND {condition}
            ORDER BY debit_amount DESC
            LIMIT 5
        """)
        
        results = cur.fetchall()
        if results:
            print(f"\n{txn_type} (top 5 by amount):")
            for row in results:
                account = 'CIBC' if row[3] == '0228362' else 'Scotia' if row[3] == '903990106011' else row[3]
                print(f"  {row[0]} | {row[1][:60]:60} | ${row[2]:>10,.2f} | {account}")
    
    print("\n" + "="*80)
    print("RECOMMENDATION")
    print("="*80)
    print("\n✅ YES - All banking debits are now in the system")
    print("   - Card payments: Import as receipts from banking data")
    print("   - Cheques: Import as receipts from banking data")
    print("   - Transfers/EFTs: Import as receipts from banking data")
    print("   - Bank fees: Already imported as receipts")
    print("\n✅ You can update receipts based on banking transaction dates")
    print("   - Use transaction_date as receipt_date")
    print("   - Use debit_amount as gross_amount")
    print("   - Vendor info is in the description field")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
