"""
Audit QuickBooks Online (QBO) payments for years 2013-2015.
Mirrors the 2012 audit process:
- Count QBO payments by method (cash/credit_card)
- Check for duplicates against banking_transactions
- Analyze data quality (missing charter_id, reserve_number, etc.)
- Identify banking matches
- Generate recommendations
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import sys
from datetime import datetime, timedelta

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def analyze_qbo_year(cur, year):
    """Analyze QBO payments for a specific year."""
    print(f"\n{'='*80}")
    print(f"QBO AUDIT FOR {year}")
    print(f"{'='*80}\n")
    
    results = {}
    
    # 1. Count total QBO payments by method
    print(f"1. QBO Payment Breakdown for {year}")
    print("-" * 60)
    
    cur.execute("""
        SELECT 
            payment_method,
            COUNT(*) as count,
            SUM(amount) as total_amount
        FROM payments
        WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) = %s
        AND (notes ILIKE '%%QBO Import%%' OR notes ILIKE '%%QuickBooks%%')
        GROUP BY payment_method
        ORDER BY count DESC
    """, (year,))
    
    qbo_payments = cur.fetchall()
    total_qbo = sum(row['count'] for row in qbo_payments)
    total_amount = sum(row['total_amount'] or 0 for row in qbo_payments)
    
    results['total_qbo'] = total_qbo
    results['total_amount'] = total_amount
    results['by_method'] = qbo_payments
    
    for row in qbo_payments:
        print(f"  {row['payment_method']}: {row['count']} payments (${row['total_amount']:,.2f})")
    print(f"\n  TOTAL: {total_qbo} payments (${total_amount:,.2f})")
    
    # 2. Check for duplicates against banking
    print(f"\n2. Duplicate Check Against Banking Transactions")
    print("-" * 60)
    
    # Exact date + amount matches
    cur.execute("""
        SELECT 
            p.payment_id,
            p.payment_date,
            p.amount,
            p.payment_method,
            bt.transaction_id,
            bt.transaction_date,
            bt.credit_amount,
            bt.description
        FROM payments p
        JOIN banking_transactions bt ON 
            p.payment_date = bt.transaction_date
            AND p.amount = bt.credit_amount
        WHERE EXTRACT(YEAR FROM CAST(p.payment_date AS timestamp)) = %s
        AND (p.notes ILIKE '%%QBO Import%%' OR p.notes ILIKE '%%QuickBooks%%')
        AND bt.credit_amount > 0
    """, (year,))
    
    exact_matches = cur.fetchall()
    
    # Near date matches (±3 days)
    cur.execute("""
        SELECT 
            p.payment_id,
            p.payment_date,
            p.amount,
            p.payment_method,
            bt.transaction_id,
            bt.transaction_date,
            bt.credit_amount,
            bt.description,
            ABS(EXTRACT(DAY FROM p.payment_date - bt.transaction_date)) as day_diff
        FROM payments p
        JOIN banking_transactions bt ON 
            p.amount = bt.credit_amount
            AND ABS(EXTRACT(DAY FROM p.payment_date - bt.transaction_date)) BETWEEN 1 AND 3
        WHERE EXTRACT(YEAR FROM CAST(p.payment_date AS timestamp)) = %s
        AND (p.notes ILIKE '%%QBO Import%%' OR p.notes ILIKE '%%QuickBooks%%')
        AND bt.credit_amount > 0
    """, (year,))
    
    near_matches = cur.fetchall()
    
    exact_dup_count = len(exact_matches)
    exact_dup_amount = sum(row['amount'] for row in exact_matches)
    near_dup_count = len(near_matches)
    near_dup_amount = sum(row['amount'] for row in near_matches)
    
    results['exact_duplicates'] = exact_dup_count
    results['exact_dup_amount'] = exact_dup_amount
    results['near_duplicates'] = near_dup_count
    results['near_dup_amount'] = near_dup_amount
    
    print(f"  Exact matches (same date + amount): {exact_dup_count} (${exact_dup_amount:,.2f})")
    print(f"  Near matches (±3 days, same amount): {near_dup_count} (${near_dup_amount:,.2f})")
    
    if exact_dup_count > 0:
        print(f"\n  Sample exact duplicates:")
        for row in exact_matches[:5]:
            print(f"    Payment {row['payment_id']} ({row['payment_date']}) ${row['amount']:.2f}")
            print(f"      → Banking {row['transaction_id']} ({row['transaction_date']}) ${row['credit_amount']:.2f}")
    
    # 3. Check banking matches already noted
    print(f"\n3. Banking Matches Already Recorded")
    print("-" * 60)
    
    cur.execute("""
        SELECT COUNT(*) as matched_count,
               SUM(amount) as matched_amount
        FROM payments
        WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) = %s
        AND (notes ILIKE '%%QBO Import%%' OR notes ILIKE '%%QuickBooks%%')
        AND (notes ILIKE '%%matched to banking%%' OR notes ILIKE '%%CIBC%%')
    """, (year,))
    
    matched = cur.fetchone()
    results['already_matched'] = matched['matched_count']
    results['already_matched_amount'] = matched['matched_amount'] or 0
    
    print(f"  Already matched: {matched['matched_count']} payments (${matched['matched_amount'] or 0:,.2f})")
    
    # 4. Data quality analysis
    print(f"\n4. Data Quality Analysis")
    print("-" * 60)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(charter_id) as has_charter,
            COUNT(reserve_number) as has_reserve,
            COUNT(client_id) as has_client,
            COUNT(CASE WHEN notes IS NULL OR notes = '' THEN 1 END) as no_notes
        FROM payments
        WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) = %s
        AND (notes ILIKE '%%QBO Import%%' OR notes ILIKE '%%QuickBooks%%')
    """, (year,))
    
    quality = cur.fetchone()
    
    results['quality'] = quality
    
    print(f"  Total QBO payments: {quality['total']}")
    print(f"  With charter_id: {quality['has_charter']} ({quality['has_charter']/quality['total']*100:.1f}%)")
    print(f"  With reserve_number: {quality['has_reserve']} ({quality['has_reserve']/quality['total']*100:.1f}%)")
    print(f"  With client_id: {quality['has_client']} ({quality['has_client']/quality['total']*100:.1f}%)")
    print(f"  Without notes: {quality['no_notes']}")
    
    # 5. Check for within-QBO duplicates
    print(f"\n5. Within-QBO Duplicate Check")
    print("-" * 60)
    
    cur.execute("""
        SELECT 
            payment_date,
            amount,
            payment_method,
            COUNT(*) as dup_count,
            ARRAY_AGG(payment_id) as payment_ids
        FROM payments
        WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) = %s
        AND (notes ILIKE '%%QBO Import%%' OR notes ILIKE '%%QuickBooks%%')
        GROUP BY payment_date, amount, payment_method
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC, amount DESC
    """, (year,))
    
    internal_dups = cur.fetchall()
    
    results['internal_duplicates'] = len(internal_dups)
    
    if internal_dups:
        print(f"  Found {len(internal_dups)} duplicate groups within QBO imports:")
        for row in internal_dups[:10]:
            print(f"    {row['payment_date']} ${row['amount']:.2f} ({row['payment_method']}): {row['dup_count']} occurrences")
            print(f"      Payment IDs: {row['payment_ids']}")
    else:
        print(f"  No internal duplicates found")
    
    return results

def generate_summary(all_results):
    """Generate summary across all years."""
    print(f"\n{'='*80}")
    print(f"MULTI-YEAR SUMMARY (2013-2015)")
    print(f"{'='*80}\n")
    
    total_qbo = sum(r['total_qbo'] for r in all_results.values())
    total_amount = sum(r['total_amount'] for r in all_results.values())
    total_exact_dups = sum(r['exact_duplicates'] for r in all_results.values())
    total_exact_dup_amt = sum(r['exact_dup_amount'] for r in all_results.values())
    total_already_matched = sum(r['already_matched'] for r in all_results.values())
    total_internal_dups = sum(r['internal_duplicates'] for r in all_results.values())
    
    print(f"Total QBO payments (2013-2015): {total_qbo} (${total_amount:,.2f})")
    print(f"Exact banking duplicates: {total_exact_dups} (${total_exact_dup_amt:,.2f})")
    print(f"Already matched to banking: {total_already_matched}")
    print(f"Internal duplicate groups: {total_internal_dups}")
    
    print(f"\nYear-by-Year Breakdown:")
    print("-" * 60)
    for year in sorted(all_results.keys()):
        r = all_results[year]
        print(f"  {year}: {r['total_qbo']} payments (${r['total_amount']:,.2f})")
        print(f"    - Exact dups vs banking: {r['exact_duplicates']} (${r['exact_dup_amount']:,.2f})")
        print(f"    - Already matched: {r['already_matched']}")
        print(f"    - Charter linked: {r['quality']['has_charter']}/{r['total_qbo']}")
        print(f"    - Internal dups: {r['internal_duplicates']}")
    
    # Recommendations
    print(f"\nRECOMMENDATIONS:")
    print("-" * 60)
    
    if total_exact_dups > 0:
        print(f"  1. Mark {total_exact_dups} exact duplicate payments (${total_exact_dup_amt:,.2f})")
        print(f"     → These match verified banking transactions and should be flagged")
    
    unmatched_qbo = total_qbo - total_already_matched - total_exact_dups
    if unmatched_qbo > 0:
        print(f"  2. Review ~{unmatched_qbo} unmatched QBO payments")
        print(f"     → Likely merchant batch settlements needing processor reconciliation")
    
    if total_internal_dups > 0:
        print(f"  3. Investigate {total_internal_dups} internal duplicate groups")
        print(f"     → Multiple QBO imports of same transaction?")
    
    # Check charter linkage quality
    avg_charter_pct = sum(r['quality']['has_charter']/r['total_qbo']*100 for r in all_results.values()) / len(all_results)
    if avg_charter_pct < 10:
        print(f"  4. Charter linkage is low (~{avg_charter_pct:.1f}% average)")
        print(f"     → This is expected for merchant batch settlements")
        print(f"     → Focus on settlement-level reconciliation instead")

def main():
    """Main execution."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    years = [2013, 2014, 2015]
    all_results = {}
    
    try:
        for year in years:
            all_results[year] = analyze_qbo_year(cur, year)
        
        generate_summary(all_results)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        cur.close()
        conn.close()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
