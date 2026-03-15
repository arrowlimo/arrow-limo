"""
Audit 2012-2014 receipts matching to banking records.
Check if banking fees, cash withdrawals, deposits are recorded as receipts.
"""
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("\n" + "=" * 100)
    print("2012-2014 RECEIPTS TO BANKING RECONCILIATION AUDIT")
    print("=" * 100)
    
    for year in [2012, 2013, 2014]:
        print(f"\n{'=' * 100}")
        print(f"YEAR {year}")
        print("=" * 100)
        
        # 1. Receipt counts
        cur.execute("""
            SELECT 
                COUNT(*) as total_receipts,
                COUNT(CASE WHEN mapped_bank_account_id IS NOT NULL THEN 1 END) as receipts_with_bank_link,
                COUNT(CASE WHEN created_from_banking = TRUE THEN 1 END) as receipts_from_banking,
                SUM(gross_amount) as total_amount,
                SUM(CASE WHEN mapped_bank_account_id IS NOT NULL THEN gross_amount ELSE 0 END) as linked_amount
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = %s
        """, (year,))
        receipt_summary = cur.fetchone()
        
        print(f"\n📝 RECEIPTS OVERVIEW:")
        print(f"   Total Receipts: {receipt_summary['total_receipts']:,}")
        print(f"   With Bank Link: {receipt_summary['receipts_with_bank_link']:,} ({receipt_summary['receipts_with_bank_link']/receipt_summary['total_receipts']*100:.1f}%)")
        print(f"   Created from Banking: {receipt_summary['receipts_from_banking']:,}")
        print(f"   Total Amount: ${receipt_summary['total_amount']:,.2f}")
        print(f"   Linked Amount: ${receipt_summary['linked_amount']:,.2f}")
        
        # 2. Banking-Receipt junction table links
        cur.execute("""
            SELECT 
                COUNT(DISTINCT bm.receipt_id) as receipts_matched,
                COUNT(DISTINCT bm.banking_transaction_id) as banking_txns_matched,
                COUNT(*) as total_links
            FROM banking_receipt_matching_ledger bm
            JOIN receipts r ON r.receipt_id = bm.receipt_id
            WHERE EXTRACT(YEAR FROM r.receipt_date) = %s
        """, (year,))
        junction_summary = cur.fetchone()
        
        print(f"\n🔗 JUNCTION TABLE (banking_receipt_matching_ledger):")
        print(f"   Receipts Matched: {junction_summary['receipts_matched']:,}")
        print(f"   Banking Txns Matched: {junction_summary['banking_txns_matched']:,}")
        print(f"   Total Links: {junction_summary['total_links']:,}")
        
        # 3. Banking fees recorded as receipts
        cur.execute("""
            SELECT 
                COUNT(*) as fee_count,
                SUM(gross_amount) as total_fees
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = %s
            AND category = 'bank_fees'
        """, (year,))
        fees = cur.fetchone()
        
        print(f"\n💳 BANKING FEES IN RECEIPTS:")
        print(f"   Fee Receipts: {fees['fee_count']:,}")
        print(f"   Total Fees: ${fees['total_fees'] or 0:,.2f}")
        
        # Check banking transactions for fees NOT in receipts
        cur.execute("""
            SELECT 
                COUNT(*) as fee_txns,
                SUM(COALESCE(debit_amount, 0)) as total_fee_amount
            FROM banking_transactions bt
            WHERE EXTRACT(YEAR FROM transaction_date) = %s
            AND (
                UPPER(description) LIKE '%%FEE%%'
                OR UPPER(description) LIKE '%%SERVICE CHARGE%%'
                OR UPPER(description) LIKE '%%NSF%%'
                OR UPPER(description) LIKE '%%OVERDRAFT%%'
            )
            AND NOT EXISTS (
                SELECT 1 FROM banking_receipt_matching_ledger bm
                WHERE bm.banking_transaction_id = bt.transaction_id
            )
        """, (year,))
        unmatched_fees = cur.fetchone()
        
        if unmatched_fees['fee_txns'] > 0:
            print(f"\n   ⚠️  UNMATCHED BANKING FEES:")
            print(f"      Transactions: {unmatched_fees['fee_txns']}")
            print(f"      Amount: ${unmatched_fees['total_fee_amount'] or 0:,.2f}")
        else:
            print(f"\n   ✅ All banking fees matched to receipts")
        
        # 4. Cash withdrawals
        cur.execute("""
            SELECT 
                COUNT(*) as cash_withdrawals,
                SUM(COALESCE(debit_amount, 0)) as total_cash
            FROM banking_transactions
            WHERE EXTRACT(YEAR FROM transaction_date) = %s
            AND (
                UPPER(description) LIKE '%%CASH%%'
                OR UPPER(description) LIKE '%%ATM%%'
                OR UPPER(description) LIKE '%%WITHDRAW%%'
            )
        """, (year,))
        cash = cur.fetchone()
        
        print(f"\n💵 CASH WITHDRAWALS:")
        print(f"   Banking Transactions: {cash['cash_withdrawals']:,}")
        print(f"   Total Amount: ${cash['total_cash'] or 0:,.2f}")
        
        # Check if cash withdrawals have receipts
        cur.execute("""
            SELECT 
                COUNT(*) as unmatched_cash
            FROM banking_transactions bt
            WHERE EXTRACT(YEAR FROM transaction_date) = %s
            AND (
                UPPER(description) LIKE '%%CASH%%'
                OR UPPER(description) LIKE '%%ATM%%'
            )
            AND NOT EXISTS (
                SELECT 1 FROM banking_receipt_matching_ledger bm
                WHERE bm.banking_transaction_id = bt.transaction_id
            )
        """, (year,))
        unmatched_cash = cur.fetchone()
        
        if unmatched_cash['unmatched_cash'] > 0:
            print(f"   ⚠️  Unmatched: {unmatched_cash['unmatched_cash']} withdrawals without receipts")
        else:
            print(f"   ✅ All cash withdrawals matched")
        
        # 5. Deposits (credits)
        cur.execute("""
            SELECT 
                COUNT(*) as deposit_count,
                SUM(COALESCE(credit_amount, 0)) as total_deposits
            FROM banking_transactions
            WHERE EXTRACT(YEAR FROM transaction_date) = %s
            AND COALESCE(credit_amount, 0) > 0
        """, (year,))
        deposits = cur.fetchone()
        
        print(f"\n💰 DEPOSITS (CREDITS):")
        print(f"   Banking Transactions: {deposits['deposit_count']:,}")
        print(f"   Total Amount: ${deposits['total_deposits'] or 0:,.2f}")
        
        # 6. Unmatched banking transactions (debits only)
        cur.execute("""
            SELECT 
                COUNT(*) as unmatched_debits,
                SUM(COALESCE(debit_amount, 0)) as unmatched_amount
            FROM banking_transactions bt
            WHERE EXTRACT(YEAR FROM transaction_date) = %s
            AND COALESCE(debit_amount, 0) > 0
            AND NOT EXISTS (
                SELECT 1 FROM banking_receipt_matching_ledger bm
                WHERE bm.banking_transaction_id = bt.transaction_id
            )
        """, (year,))
        unmatched = cur.fetchone()
        
        print(f"\n⚠️  UNMATCHED BANKING DEBITS (No Receipt):")
        print(f"   Transactions: {unmatched['unmatched_debits']:,}")
        print(f"   Amount: ${unmatched['unmatched_amount'] or 0:,.2f}")
        
        # 7. Sample unmatched transactions
        if unmatched['unmatched_debits'] > 0:
            cur.execute("""
                SELECT 
                    transaction_date,
                    description,
                    debit_amount,
                    account_number
                FROM banking_transactions bt
                WHERE EXTRACT(YEAR FROM transaction_date) = %s
                AND COALESCE(debit_amount, 0) > 0
                AND NOT EXISTS (
                    SELECT 1 FROM banking_receipt_matching_ledger bm
                    WHERE bm.banking_transaction_id = bt.transaction_id
                )
                ORDER BY debit_amount DESC
                LIMIT 10
            """, (year,))
            samples = cur.fetchall()
            
            print(f"\n   Top 10 Unmatched Debits:")
            for s in samples:
                print(f"      {s['transaction_date']} | ${s['debit_amount']:>8,.2f} | {s['description'][:60]}")
        
        # 8. Category breakdown of receipts
        cur.execute("""
            SELECT 
                category,
                COUNT(*) as count,
                SUM(gross_amount) as total
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = %s
            GROUP BY category
            ORDER BY total DESC
            LIMIT 15
        """, (year,))
        categories = cur.fetchall()
        
        print(f"\n📊 TOP RECEIPT CATEGORIES:")
        for cat in categories:
            cat_name = cat['category'] or 'uncategorized'
            print(f"   {cat_name:<30} {cat['count']:>5} receipts  ${cat['total']:>12,.2f}")
    
    # Summary across all years
    print("\n" + "=" * 100)
    print("SUMMARY 2012-2014")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as receipts,
            COUNT(CASE WHEN mapped_bank_account_id IS NOT NULL THEN 1 END) as linked,
            SUM(gross_amount) as total
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2012 AND 2014
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    summary = cur.fetchall()
    
    print(f"\n{'Year':<6} {'Receipts':<10} {'Linked':<10} {'Link %':<10} {'Total Amount':<15}")
    print("-" * 100)
    for row in summary:
        link_pct = (row['linked'] / row['receipts'] * 100) if row['receipts'] > 0 else 0
        print(f"{int(row['year']):<6} {row['receipts']:<10,} {row['linked']:<10,} {link_pct:<10.1f} ${row['total']:<14,.2f}")
    
    # Overall totals
    cur.execute("""
        SELECT 
            COUNT(*) as total_receipts,
            COUNT(CASE WHEN mapped_bank_account_id IS NOT NULL THEN 1 END) as total_linked,
            SUM(gross_amount) as total_amount
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2012 AND 2014
    """)
    overall = cur.fetchone()
    
    print(f"\n{'TOTAL':<6} {overall['total_receipts']:<10,} {overall['total_linked']:<10,} {overall['total_linked']/overall['total_receipts']*100:<10.1f} ${overall['total_amount']:<14,.2f}")
    
    # Action items
    print("\n" + "=" * 100)
    print("ACTION ITEMS")
    print("=" * 100)
    
    cur.execute("""
        SELECT COUNT(*) as unmatched FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) BETWEEN 2012 AND 2014
        AND debit_amount > 0
        AND NOT EXISTS (
            SELECT 1 FROM banking_receipt_matching_ledger bm
            WHERE bm.banking_transaction_id = transaction_id
        )
    """)
    total_unmatched = cur.fetchone()['unmatched']
    
    if total_unmatched > 0:
        print(f"\n⚠️  {total_unmatched:,} banking debits without receipts")
        print("   Consider running: python scripts/auto_create_receipts_from_all_banking.py --year 2012-2014")
    else:
        print("\n✅ All banking transactions matched to receipts")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
