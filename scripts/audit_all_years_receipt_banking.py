"""
Audit ALL YEARS receipts matching to banking records.
Check if banking fees, cash withdrawals, deposits are recorded in receipts.
"""
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def audit_year(cur, year):
    """Audit a single year."""
    print(f"\n{'=' * 100}")
    print(f"YEAR {year}")
    print("=" * 100)
    
    # 1. Receipt counts
    cur.execute("""
        SELECT 
            COUNT(*) as total_receipts,
            COUNT(CASE WHEN mapped_bank_account_id IS NOT NULL THEN 1 END) as receipts_with_bank_link,
            COUNT(CASE WHEN created_from_banking = TRUE THEN 1 END) as receipts_from_banking,
            SUM(COALESCE(gross_amount, 0)) as total_amount,
            SUM(CASE WHEN mapped_bank_account_id IS NOT NULL THEN COALESCE(gross_amount, 0) ELSE 0 END) as linked_amount
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = %s
    """, (year,))
    receipt_summary = cur.fetchone()
    
    if receipt_summary['total_receipts'] == 0:
        print(f"\n❌ No receipts in database")
        return None
    
    print(f"\nRECEIPTS: {receipt_summary['total_receipts']:,} | "
          f"Linked: {receipt_summary['receipts_with_bank_link']:,} ({receipt_summary['receipts_with_bank_link']/receipt_summary['total_receipts']*100:.0f}%) | "
          f"From Banking: {receipt_summary['receipts_from_banking']:,} | "
          f"Amount: ${receipt_summary['total_amount']:,.0f}")
    
    # 2. Banking transactions
    cur.execute("""
        SELECT 
            COUNT(*) as total_txns,
            COUNT(CASE WHEN COALESCE(debit_amount, 0) > 0 THEN 1 END) as debits,
            COUNT(CASE WHEN COALESCE(credit_amount, 0) > 0 THEN 1 END) as credits,
            SUM(COALESCE(debit_amount, 0)) as total_debits,
            SUM(COALESCE(credit_amount, 0)) as total_credits
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = %s
    """, (year,))
    banking_summary = cur.fetchone()
    
    if banking_summary['total_txns'] == 0:
        print(f"BANKING: [X] No transactions")
        return None
    
    print(f"BANKING: {banking_summary['total_txns']:,} txns | "
          f"Debits: ${banking_summary['total_debits']:,.0f} | "
          f"Credits: ${banking_summary['total_credits']:,.0f}")
    
    # 3. Matching stats
    cur.execute("""
        SELECT 
            COUNT(DISTINCT bm.receipt_id) as receipts_matched,
            COUNT(DISTINCT bm.banking_transaction_id) as banking_matched
        FROM banking_receipt_matching_ledger bm
        JOIN receipts r ON r.receipt_id = bm.receipt_id
        WHERE EXTRACT(YEAR FROM r.receipt_date) = %s
    """, (year,))
    matching = cur.fetchone()
    
    print(f"MATCHED: {matching['receipts_matched']:,} receipts <-> {matching['banking_matched']:,} banking txns")
    
    # 4. Unmatched debits
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
    
    if unmatched['unmatched_debits'] > 0:
        print(f"[!] UNMATCHED: {unmatched['unmatched_debits']:,} banking debits (${unmatched['unmatched_amount']:,.0f}) have NO receipts")
    else:
        print(f"[OK] All banking debits matched")
    
    # 5. Banking fees
    cur.execute("""
        SELECT COUNT(*) as fee_count, SUM(COALESCE(gross_amount, 0)) as total
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = %s
        AND category = 'bank_fees'
    """, (year,))
    fees = cur.fetchone()
    
    if banking_summary['total_txns'] > 0:
        cur.execute("""
            SELECT COUNT(*) as unmatched
            FROM banking_transactions bt
            WHERE EXTRACT(YEAR FROM transaction_date) = %s
            AND (UPPER(COALESCE(description, '')) LIKE '%%FEE%%' OR UPPER(COALESCE(description, '')) LIKE '%%SERVICE CHARGE%%')
            AND NOT EXISTS (SELECT 1 FROM banking_receipt_matching_ledger bm WHERE bm.banking_transaction_id = bt.transaction_id)
        """, (year,))
        unmatched_fees = cur.fetchone()
        
        if fees['fee_count'] > 0:
            print(f"FEES: {fees['fee_count']} receipts (${fees['total']:,.0f}) | Unmatched: {unmatched_fees['unmatched']}")
        elif unmatched_fees['unmatched'] > 0:
            print(f"[!] FEES: {unmatched_fees['unmatched']} banking fees have NO receipts")
    
    return {
        'year': year,
        'receipts': receipt_summary['total_receipts'],
        'receipts_linked': receipt_summary['receipts_with_bank_link'],
        'banking_txns': banking_summary['total_txns'],
        'banking_debits': banking_summary['debits'],
        'matched_receipts': matching['receipts_matched'],
        'unmatched_debits': unmatched['unmatched_debits'],
        'unmatched_amount': unmatched['unmatched_amount']
    }

def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("\n" + "=" * 100)
    print("ALL YEARS RECEIPTS TO BANKING RECONCILIATION AUDIT")
    print("=" * 100)
    
    results = []
    
    for year in range(2007, 2026):
        result = audit_year(cur, year)
        if result:
            results.append(result)
    
    # Summary table
    print("\n" + "=" * 100)
    print("SUMMARY TABLE")
    print("=" * 100)
    print(f"\n{'Year':<6} {'Receipts':<10} {'Linked':<10} {'Link%':<8} {'Banking':<10} {'Matched':<10} {'Unmatched':<12} {'Amount':<15}")
    print("-" * 100)
    
    total_receipts = 0
    total_linked = 0
    total_banking = 0
    total_matched = 0
    total_unmatched = 0
    total_amount = 0
    
    for r in results:
        link_pct = (r['receipts_linked'] / r['receipts'] * 100) if r['receipts'] > 0 else 0
        total_receipts += r['receipts']
        total_linked += r['receipts_linked']
        total_banking += r['banking_txns']
        total_matched += r['matched_receipts']
        total_unmatched += r['unmatched_debits']
        total_amount += r['unmatched_amount'] or 0
        
        status = "[OK]" if r['unmatched_debits'] == 0 else "[!]"
        unmatched_amt = r['unmatched_amount'] or 0
        print(f"{r['year']:<6} {r['receipts']:<10,} {r['receipts_linked']:<10,} {link_pct:<7.0f}% {r['banking_txns']:<10,} "
              f"{r['matched_receipts']:<10,} {r['unmatched_debits']:<12,} ${unmatched_amt:<14,.0f} {status}")
    
    print("-" * 100)
    avg_link = (total_linked / total_receipts * 100) if total_receipts > 0 else 0
    print(f"{'TOTAL':<6} {total_receipts:<10,} {total_linked:<10,} {avg_link:<7.0f}% {total_banking:<10,} "
          f"{total_matched:<10,} {total_unmatched:<12,} ${total_amount:<14,.0f}")
    
    # Years needing work
    print("\n" + "=" * 100)
    print("PRIORITY ACTION ITEMS")
    print("=" * 100)
    
    needs_work = [r for r in results if r['unmatched_debits'] > 0]
    needs_work.sort(key=lambda x: x['unmatched_amount'], reverse=True)
    
    if needs_work:
        print(f"\n[!] {len(needs_work)} years have unmatched banking transactions:\n")
        for r in needs_work:
            print(f"   {r['year']}: {r['unmatched_debits']:,} unmatched debits (${r['unmatched_amount']:,.0f})")
        
        print(f"\n   TOTAL UNMATCHED: {total_unmatched:,} transactions (${total_amount:,.0f})")
        print(f"\n   Run: python scripts/match_all_receipts_to_banking.py --write")
        print(f"   Then: python scripts/auto_create_receipts_from_all_banking.py --write")
    else:
        print("\n[OK] All years have complete receipt-to-banking matching!")
    
    # No data years
    print("\n" + "=" * 100)
    print("YEARS WITH NO DATA")
    print("=" * 100)
    
    all_years = set(range(2007, 2026))
    years_with_data = set(r['year'] for r in results)
    no_data = sorted(all_years - years_with_data)
    
    if no_data:
        print(f"\n[X] {len(no_data)} years have no receipts or banking data:")
        print(f"   {', '.join(map(str, no_data))}")
        print(f"\n   ACTION: Import banking statements and create receipts")
    else:
        print("\n[OK] All years 2007-2025 have data!")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
