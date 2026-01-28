"""
Assess Scotia Bank 2012 transaction and receipt status
"""
import psycopg2
import sys

def main():
    print("=" * 80)
    print("SCOTIA BANK 2012 STATUS ASSESSMENT")
    print("=" * 80)
    
    # Connect to database
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()
    
    try:
        # Check banking transactions
        print("\n1. BANKING TRANSACTIONS (Scotia Account #903990106011)")
        print("-" * 80)
        
        cur.execute("""
            SELECT 
                COUNT(*),
                MIN(transaction_date),
                MAX(transaction_date),
                SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END) as total_deposits,
                SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END) as total_withdrawals
            FROM banking_transactions
            WHERE account_number = '903990106011'
            AND EXTRACT(YEAR FROM transaction_date) = 2012
        """)
        
        result = cur.fetchone()
        print(f"  Total transactions: {result[0]:,}")
        print(f"  Date range: {result[1]} to {result[2]}")
        print(f"  Total deposits: ${result[3]:,.2f}" if result[3] else "  Total deposits: $0.00")
        print(f"  Total withdrawals: ${result[4]:,.2f}" if result[4] else "  Total withdrawals: $0.00")
        
        # Check receipts
        print("\n2. RECEIPTS (Scotia Account)")
        print("-" * 80)
        
        cur.execute("""
            SELECT 
                COUNT(*),
                MIN(receipt_date),
                MAX(receipt_date),
                SUM(gross_amount) as total_amount
            FROM receipts
            WHERE mapped_bank_account_id = 2
            AND EXTRACT(YEAR FROM receipt_date) = 2012
        """)
        
        result = cur.fetchone()
        total_receipts = result[0]
        print(f"  Total receipts: {result[0]:,}")
        print(f"  Date range: {result[1]} to {result[2]}")
        print(f"  Total amount: ${result[3]:,.2f}" if result[3] else "  Total amount: $0.00")
        
        # Check matching status
        print("\n3. RECEIPT-BANKING MATCHING STATUS")
        print("-" * 80)
        
        cur.execute("""
            SELECT COUNT(*)
            FROM receipts
            WHERE mapped_bank_account_id = 2
            AND EXTRACT(YEAR FROM receipt_date) = 2012
            AND banking_transaction_id IS NOT NULL
        """)
        
        matched_receipts = cur.fetchone()[0]
        unmatched_receipts = total_receipts - matched_receipts
        
        print(f"  Matched receipts: {matched_receipts:,} ({matched_receipts/total_receipts*100:.1f}%)" if total_receipts > 0 else "  Matched receipts: 0")
        print(f"  Unmatched receipts: {unmatched_receipts:,} ({unmatched_receipts/total_receipts*100:.1f}%)" if total_receipts > 0 else "  Unmatched receipts: 0")
        
        # Check for gaps
        print("\n4. POTENTIAL GAPS")
        print("-" * 80)
        
        cur.execute("""
            SELECT 
                DATE_TRUNC('month', receipt_date) as month,
                COUNT(*) as receipt_count,
                SUM(gross_amount) as total_amount
            FROM receipts
            WHERE mapped_bank_account_id = 2
            AND EXTRACT(YEAR FROM receipt_date) = 2012
            GROUP BY DATE_TRUNC('month', receipt_date)
            ORDER BY month
        """)
        
        monthly_receipts = cur.fetchall()
        print("  Monthly receipt breakdown:")
        for row in monthly_receipts:
            print(f"    {row[0].strftime('%Y-%m')}: {row[1]:,} receipts, ${row[2]:,.2f}")
        
        # Check banking transaction sources
        print("\n5. BANKING TRANSACTION SOURCES")
        print("-" * 80)
        
        cur.execute("""
            SELECT 
                'Scotia' as source,
                COUNT(*) as count,
                SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END) as deposits,
                SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END) as withdrawals
            FROM banking_transactions
            WHERE account_number = '903990106011'
            AND EXTRACT(YEAR FROM transaction_date) = 2012
        """)
        
        sources = cur.fetchall()
        print("  Transaction sources:")
        for row in sources:
            print(f"    {row[0]}: {row[1]:,} transactions (Deposits: ${row[2]:,.2f}, Withdrawals: ${row[3]:,.2f})")
        
        # Check for unlinked banking transactions
        print("\n6. UNLINKED BANKING TRANSACTIONS")
        print("-" * 80)
        
        cur.execute("""
            SELECT 
                COUNT(*),
                SUM(debit_amount)
            FROM banking_transactions
            WHERE account_number = '903990106011'
            AND EXTRACT(YEAR FROM transaction_date) = 2012
            AND debit_amount > 0
            AND receipt_id IS NULL
        """)
        
        result = cur.fetchone()
        unlinked_banking = result[0]
        unlinked_amount = result[1] if result[1] else 0
        print(f"  Banking transactions (debits) without receipts: {unlinked_banking:,} (${unlinked_amount:,.2f})")
        
        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY & RECOMMENDATIONS")
        print("=" * 80)
        
        if total_receipts == 0:
            print("  ❌ NO SCOTIA RECEIPTS FOUND FOR 2012")
            print("  📝 Action: Import Scotia 2012 receipts from source documents")
        elif unmatched_receipts > total_receipts * 0.5:
            print(f"  ⚠️  HIGH UNMATCH RATE: {unmatched_receipts/total_receipts*100:.1f}% receipts unmatched")
            print("  📝 Action: Run receipt-banking reconciliation script")
        else:
            print(f"  ✅ MATCH RATE: {matched_receipts/total_receipts*100:.1f}% receipts matched to banking")
        
        if unlinked_banking > 0:
            print(f"  ⚠️  {unlinked_banking:,} banking transactions without receipts")
            print("  📝 Action: Review unlinked transactions for missing receipts")
        
        print("\n✅ ASSESSMENT COMPLETE")
        
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
