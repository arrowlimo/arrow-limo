"""
COMPLETE PAYMENT IMPORT AUDIT SUMMARY (2012-2024)
Consolidates findings from:
- 2012 QBO audit
- 2013-2015 LMS audit  
- 2016-2024 comprehensive audit
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
    
    print("="*80)
    print("COMPLETE PAYMENT IMPORT AUDIT SUMMARY (2012-2024)")
    print("="*80)
    
    # Aggregate statistics by type and period
    periods = {
        '2012': ('QBO Only', 2012, 2012),
        '2013-2015': ('LMS Only', 2013, 2015),
        '2016-2024': ('LMS + Square', 2016, 2024)
    }
    
    overall_stats = {}
    
    for period_name, (label, start_year, end_year) in periods.items():
        print(f"\n{period_name} ({label})")
        print("-" * 60)
        
        # QBO
        cur.execute("""
            SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as total
            FROM payments
            WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) BETWEEN %s AND %s
            AND (notes ILIKE '%%QBO%%' OR notes ILIKE '%%QuickBooks Online%%')
        """, (start_year, end_year))
        qbo = cur.fetchone()
        
        # LMS
        cur.execute("""
            SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as total
            FROM payments
            WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) BETWEEN %s AND %s
            AND notes ILIKE '%%Imported from LMS%%'
        """, (start_year, end_year))
        lms = cur.fetchone()
        
        # Square
        cur.execute("""
            SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as total
            FROM payments
            WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) BETWEEN %s AND %s
            AND (notes ILIKE '%%Square%%' OR square_transaction_id IS NOT NULL)
        """, (start_year, end_year))
        square = cur.fetchone()
        
        # Charter linkage
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(reserve_number) as has_reserve
            FROM payments
            WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) BETWEEN %s AND %s
            AND (
                notes ILIKE '%%Import%%' 
                OR notes ILIKE '%%QBO%%' 
                OR notes ILIKE '%%Square%%'
                OR square_transaction_id IS NOT NULL
            )
        """, (start_year, end_year))
        linkage = cur.fetchone()
        
        overall_stats[period_name] = {
            'qbo': qbo,
            'lms': lms,
            'square': square,
            'linkage': linkage
        }
        
        print(f"  QBO: {qbo['count']} payments (${qbo['total']:,.2f})")
        print(f"  LMS: {lms['count']} payments (${lms['total']:,.2f})")
        print(f"  Square: {square['count']} payments (${square['total']:,.2f})")
        
        if linkage['total'] > 0:
            link_pct = (linkage['has_reserve'] / linkage['total'] * 100)
            print(f"  Charter linkage: {linkage['has_reserve']}/{linkage['total']} ({link_pct:.1f}%)")
    
    # Grand totals
    print(f"\n{'='*80}")
    print(f"GRAND TOTALS (2012-2024)")
    print(f"{'='*80}\n")
    
    total_qbo = sum(s['qbo']['count'] for s in overall_stats.values())
    total_lms = sum(s['lms']['count'] for s in overall_stats.values())
    total_square = sum(s['square']['count'] for s in overall_stats.values())
    
    qbo_amt = sum(s['qbo']['total'] for s in overall_stats.values())
    lms_amt = sum(s['lms']['total'] for s in overall_stats.values())
    square_amt = sum(s['square']['total'] for s in overall_stats.values())
    
    total_imports = total_qbo + total_lms + total_square
    total_amount = qbo_amt + lms_amt + square_amt
    
    print(f"Total Import Type Breakdown:")
    print(f"  QBO (2012 only): {total_qbo} payments (${qbo_amt:,.2f})")
    print(f"  LMS (2013-2024): {total_lms} payments (${lms_amt:,.2f})")
    print(f"  Square (2016-2024): {total_square} payments (${square_amt:,.2f})")
    print(f"  TOTAL: {total_imports} payments (${total_amount:,.2f})")
    
    # Key findings
    print(f"\n{'='*80}")
    print(f"KEY FINDINGS")
    print(f"{'='*80}\n")
    
    print("1. IMPORT EVOLUTION:")
    print("   • 2012: QBO-only imports (merchant batch settlements)")
    print("   • 2013-2015: Switch to LMS correction entries")
    print("   • 2016-2024: Square payment processor dominates")
    print("   • 2021-2022: Square integration temporarily drops")
    print("   • 2024: LMS imports increase (51 payments)")
    
    print("\n2. DATA QUALITY:")
    print(f"   • 2012 QBO: 0% charter linkage (merchant settlements)")
    print(f"   • 2013-2015 LMS: 100% charter linkage (correction entries)")
    print(f"   • 2016-2024: 91.9% average charter linkage")
    print(f"   • 2024: Perfect 100% charter linkage")
    
    print("\n3. DUPLICATES IDENTIFIED:")
    print("   • 2012: 4 QBO duplicates marked (vs banking)")
    print("   • 2013-2015: 0 LMS duplicates")
    print("   • 2016-2024: 17 potential duplicate groups across 9 years")
    
    print("\n4. REFUNDS/CORRECTIONS:")
    cur.execute("""
        SELECT 
            COUNT(*) as negative_count,
            COALESCE(SUM(amount), 0) as negative_total
        FROM payments
        WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) BETWEEN 2012 AND 2024
        AND amount < 0
        AND (
            notes ILIKE '%%Import%%' 
            OR notes ILIKE '%%QBO%%' 
            OR notes ILIKE '%%Square%%'
            OR square_transaction_id IS NOT NULL
        )
    """)
    negatives = cur.fetchone()
    
    print(f"   • Total negative imports: {negatives['negative_count']} payments")
    print(f"   • Total refund amount: ${negatives['negative_total']:,.2f}")
    
    print("\n5. VOLUME TRENDS:")
    print("   • 2012: 206 imports (QBO merchant settlements)")
    print("   • 2013-2015: 95 imports (LMS corrections)")
    print("   • 2016-2019: Peak Square activity (574 payments)")
    print("   • 2020: COVID impact (127 imports, down from 176)")
    print("   • 2021-2022: Low Square usage (18-19 imports/year)")
    print("   • 2023-2024: Recovery (40-58 imports/year)")
    
    # Recommendations
    print(f"\n{'='*80}")
    print(f"RECOMMENDATIONS")
    print(f"{'='*80}\n")
    
    print("COMPLETED ACTIONS:")
    print("  ✅ 2012 QBO: 26 'cash' payments matched to banking")
    print("  ✅ 2012 QBO: 4 duplicates marked")
    print("  ✅ 2013-2015: LMS imports verified (100% linkage)")
    print("  ✅ 2016-2024: Import patterns documented")
    
    print("\nPENDING ACTIONS:")
    print("  1. Investigate 17 duplicate groups in 2016-2024")
    print("     → Focus on 2016 (6 groups) and 2023 (8 duplicate payments)")
    print("  2. Review 202 unmatched 2012 QBO merchant settlements")
    print("     → Build processor settlement reconciliation")
    print("  3. Verify Square payment reconciliation completeness")
    print("     → 746 Square payments across 2016-2024")
    print("  4. Analyze 2024 LMS import increase (51 payments)")
    print("     → Determine if new correction workflow or data migration")
    
    print(f"\n{'='*80}")
    print("AUDIT SUMMARY COMPLETE")
    print(f"{'='*80}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
