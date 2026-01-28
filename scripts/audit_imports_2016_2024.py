"""
Comprehensive audit of all payment imports (QBO and LMS) for 2016-2024.
Detects import patterns, verifies data quality, checks charter linkage.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import sys

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def audit_year_imports(cur, year):
    """Audit all imports (QBO and LMS) for a specific year."""
    print(f"\n{'='*80}")
    print(f"IMPORT AUDIT FOR {year}")
    print(f"{'='*80}\n")
    
    results = {'year': year}
    
    # 1. Detect import patterns
    print(f"1. Import Detection")
    print("-" * 60)
    
    # QBO imports
    cur.execute("""
        SELECT COUNT(*) as count, SUM(amount) as total
        FROM payments
        WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) = %s
        AND (notes ILIKE '%%QBO%%' OR notes ILIKE '%%QuickBooks Online%%')
    """, (year,))
    qbo = cur.fetchone()
    
    # LMS imports
    cur.execute("""
        SELECT COUNT(*) as count, SUM(amount) as total
        FROM payments
        WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) = %s
        AND notes ILIKE '%%Imported from LMS%%'
    """, (year,))
    lms = cur.fetchone()
    
    # Square imports
    cur.execute("""
        SELECT COUNT(*) as count, SUM(amount) as total
        FROM payments
        WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) = %s
        AND (notes ILIKE '%%Square%%' OR square_transaction_id IS NOT NULL)
    """, (year,))
    square = cur.fetchone()
    
    # Generic imports (catch-all)
    cur.execute("""
        SELECT COUNT(*) as count, SUM(amount) as total
        FROM payments
        WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) = %s
        AND notes ILIKE '%%Import%%'
        AND notes NOT ILIKE '%%LMS%%'
        AND notes NOT ILIKE '%%QBO%%'
        AND notes NOT ILIKE '%%Square%%'
    """, (year,))
    generic = cur.fetchone()
    
    results['qbo'] = qbo
    results['lms'] = lms
    results['square'] = square
    results['generic'] = generic
    
    print(f"  QBO imports: {qbo['count']} (${qbo['total'] or 0:,.2f})")
    print(f"  LMS imports: {lms['count']} (${lms['total'] or 0:,.2f})")
    print(f"  Square imports: {square['count']} (${square['total'] or 0:,.2f})")
    print(f"  Other imports: {generic['count']} (${generic['total'] or 0:,.2f})")
    
    total_imports = qbo['count'] + lms['count'] + square['count'] + generic['count']
    
    # 2. Charter linkage for all imports
    if total_imports > 0:
        print(f"\n2. Charter Linkage Analysis")
        print("-" * 60)
        
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(charter_id) as has_charter_id,
                COUNT(reserve_number) as has_reserve_number,
                COUNT(client_id) as has_client_id
            FROM payments
            WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) = %s
            AND (
                notes ILIKE '%%Import%%' 
                OR notes ILIKE '%%QBO%%' 
                OR notes ILIKE '%%Square%%'
                OR square_transaction_id IS NOT NULL
            )
        """, (year,))
        
        linkage = cur.fetchone()
        results['linkage'] = linkage
        
        print(f"  Total imports: {linkage['total']}")
        print(f"  Linked to charter_id: {linkage['has_charter_id']} ({linkage['has_charter_id']/linkage['total']*100:.1f}%)")
        print(f"  Linked to reserve_number: {linkage['has_reserve_number']} ({linkage['has_reserve_number']/linkage['total']*100:.1f}%)")
        print(f"  Linked to client_id: {linkage['has_client_id']} ({linkage['has_client_id']/linkage['total']*100:.1f}%)")
        
        # 3. Check for duplicates (within same import type)
        print(f"\n3. Duplicate Detection")
        print("-" * 60)
        
        # Check for duplicate notes patterns
        cur.execute("""
            SELECT 
                payment_date,
                amount,
                COUNT(*) as dup_count,
                ARRAY_AGG(payment_id) as payment_ids,
                MAX(notes) as sample_note
            FROM payments
            WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) = %s
            AND (
                notes ILIKE '%%Import%%' 
                OR notes ILIKE '%%QBO%%' 
                OR notes ILIKE '%%Square%%'
                OR square_transaction_id IS NOT NULL
            )
            GROUP BY payment_date, amount
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC, amount DESC
            LIMIT 10
        """, (year,))
        
        duplicates = cur.fetchall()
        results['duplicate_groups'] = len(duplicates)
        
        if duplicates:
            print(f"  Found {len(duplicates)} potential duplicate groups:")
            for dup in duplicates[:5]:
                print(f"    {dup['payment_date']} ${dup['amount']:.2f}: {dup['dup_count']} occurrences")
                print(f"      Payment IDs: {dup['payment_ids']}")
        else:
            print(f"  No duplicates detected")
        
        # 4. Negative amounts check
        print(f"\n4. Negative Amounts (Refunds/Corrections)")
        print("-" * 60)
        
        cur.execute("""
            SELECT 
                COUNT(*) as negative_count,
                SUM(amount) as negative_total
            FROM payments
            WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) = %s
            AND amount < 0
            AND (
                notes ILIKE '%%Import%%' 
                OR notes ILIKE '%%QBO%%' 
                OR notes ILIKE '%%Square%%'
                OR square_transaction_id IS NOT NULL
            )
        """, (year,))
        
        negatives = cur.fetchone()
        results['negatives'] = negatives
        
        if negatives['negative_count'] > 0:
            print(f"  Negative payments: {negatives['negative_count']} (${negatives['negative_total']:,.2f})")
        else:
            print(f"  No negative payments found")
    
    # 5. Year totals for context
    print(f"\n5. Year Overview")
    print("-" * 60)
    
    cur.execute("""
        SELECT COUNT(*) as total_payments, SUM(amount) as total_amount
        FROM payments
        WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) = %s
    """, (year,))
    
    year_total = cur.fetchone()
    results['year_total'] = year_total
    
    import_pct = (total_imports / year_total['total_payments'] * 100) if year_total['total_payments'] > 0 else 0
    
    print(f"  Total payments in {year}: {year_total['total_payments']} (${year_total['total_amount']:,.2f})")
    print(f"  Imports: {total_imports} ({import_pct:.1f}% of year)")
    
    return results

def generate_summary(all_results):
    """Generate comprehensive summary."""
    print(f"\n{'='*80}")
    print(f"COMPREHENSIVE IMPORT SUMMARY (2016-2024)")
    print(f"{'='*80}\n")
    
    # Aggregate by import type
    total_qbo = sum(r['qbo']['count'] for r in all_results.values())
    total_lms = sum(r['lms']['count'] for r in all_results.values())
    total_square = sum(r['square']['count'] for r in all_results.values())
    total_generic = sum(r['generic']['count'] for r in all_results.values())
    
    qbo_amt = sum(r['qbo']['total'] or 0 for r in all_results.values())
    lms_amt = sum(r['lms']['total'] or 0 for r in all_results.values())
    square_amt = sum(r['square']['total'] or 0 for r in all_results.values())
    generic_amt = sum(r['generic']['total'] or 0 for r in all_results.values())
    
    print(f"Total Imports by Type:")
    print("-" * 60)
    print(f"  QBO: {total_qbo} payments (${qbo_amt:,.2f})")
    print(f"  LMS: {total_lms} payments (${lms_amt:,.2f})")
    print(f"  Square: {total_square} payments (${square_amt:,.2f})")
    print(f"  Other: {total_generic} payments (${generic_amt:,.2f})")
    print(f"  TOTAL: {total_qbo + total_lms + total_square + total_generic} payments (${qbo_amt + lms_amt + square_amt + generic_amt:,.2f})")
    
    # Year-by-year trends
    print(f"\nYear-by-Year Import Trends:")
    print("-" * 60)
    print(f"{'Year':<6} {'QBO':<8} {'LMS':<8} {'Square':<8} {'Other':<8} {'Total':<8} {'% of Year':<10}")
    print("-" * 60)
    
    for year in sorted(all_results.keys()):
        r = all_results[year]
        year_imports = r['qbo']['count'] + r['lms']['count'] + r['square']['count'] + r['generic']['count']
        year_pct = (year_imports / r['year_total']['total_payments'] * 100) if r['year_total']['total_payments'] > 0 else 0
        
        print(f"{year:<6} {r['qbo']['count']:<8} {r['lms']['count']:<8} {r['square']['count']:<8} {r['generic']['count']:<8} {year_imports:<8} {year_pct:<10.1f}%")
    
    # Charter linkage quality
    print(f"\nCharter Linkage Quality:")
    print("-" * 60)
    
    years_with_imports = [r for r in all_results.values() if r.get('linkage')]
    if years_with_imports:
        avg_charter_link = sum(
            (r['linkage']['has_reserve_number'] / r['linkage']['total'] * 100) 
            for r in years_with_imports
        ) / len(years_with_imports)
        
        print(f"  Average reserve_number linkage: {avg_charter_link:.1f}%")
        
        # Show outliers
        for year in sorted(all_results.keys()):
            r = all_results[year]
            if r.get('linkage') and r['linkage']['total'] > 0:
                link_pct = r['linkage']['has_reserve_number'] / r['linkage']['total'] * 100
                if link_pct < 50 or link_pct == 100:
                    status = "⚠️" if link_pct < 50 else "✅"
                    print(f"  {status} {year}: {link_pct:.1f}% ({r['linkage']['has_reserve_number']}/{r['linkage']['total']})")
    
    # Recommendations
    print(f"\nRECOMMENDATIONS:")
    print("-" * 60)
    
    if total_qbo > 206:  # More than 2012
        print(f"  1. QBO imports found beyond 2012 ({total_qbo - 206} additional)")
        print(f"     → May need similar reconciliation as 2012")
    
    if total_square > 0:
        print(f"  2. Square payment integration active ({total_square} payments)")
        print(f"     → Verify Square reconciliation is complete")
    
    # Check for years with low linkage
    low_linkage_years = [
        year for year, r in all_results.items() 
        if r.get('linkage') and r['linkage']['total'] > 10 
        and (r['linkage']['has_reserve_number'] / r['linkage']['total'] * 100) < 75
    ]
    
    if low_linkage_years:
        print(f"  3. Low charter linkage in years: {', '.join(map(str, sorted(low_linkage_years)))}")
        print(f"     → Consider reserve_number matching improvements")

def main():
    """Main execution."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    years = range(2016, 2025)  # 2016-2024
    all_results = {}
    
    try:
        for year in years:
            all_results[year] = audit_year_imports(cur, year)
        
        generate_summary(all_results)
        
        print(f"\n{'='*80}")
        print(f"AUDIT COMPLETE")
        print(f"{'='*80}")
        
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
