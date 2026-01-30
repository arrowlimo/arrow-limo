"""
Audit LMS (Legacy Access Database) imports for 2013-2015.
Verifies data quality, charter linkage, duplicates, and consistency.
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
        password='***REDACTED***'
    )

def audit_lms_year(cur, year):
    """Audit LMS imports for a specific year."""
    print(f"\n{'='*80}")
    print(f"LMS IMPORT AUDIT FOR {year}")
    print(f"{'='*80}\n")
    
    results = {}
    
    # 1. Count and categorize LMS imports
    print(f"1. LMS Import Overview")
    print("-" * 60)
    
    cur.execute("""
        SELECT 
            payment_method,
            COUNT(*) as count,
            SUM(amount) as total_amount,
            AVG(amount) as avg_amount
        FROM payments
        WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) = %s
        AND notes ILIKE '%%Imported from LMS%%'
        GROUP BY payment_method
        ORDER BY count DESC
    """, (year,))
    
    lms_payments = cur.fetchall()
    total_lms = sum(row['count'] for row in lms_payments)
    total_amount = sum(row['total_amount'] or 0 for row in lms_payments)
    
    results['total_lms'] = total_lms
    results['total_amount'] = total_amount
    results['by_method'] = lms_payments
    
    print(f"  Total LMS imports: {total_lms} payments (${total_amount:,.2f})")
    for row in lms_payments:
        print(f"    {row['payment_method']}: {row['count']} (${row['total_amount']:,.2f}, avg ${row['avg_amount']:,.2f})")
    
    # 2. Extract LMS Payment IDs and check for patterns
    print(f"\n2. LMS Payment ID Analysis")
    print("-" * 60)
    
    cur.execute("""
        SELECT 
            payment_id,
            payment_date,
            amount,
            payment_method,
            notes,
            SUBSTRING(notes FROM 'LMS Payment ID ([0-9]+)') as lms_payment_id
        FROM payments
        WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) = %s
        AND notes ILIKE '%%Imported from LMS%%'
        ORDER BY payment_date
    """, (year,))
    
    lms_records = cur.fetchall()
    
    # Check for duplicate LMS IDs
    lms_ids = [r['lms_payment_id'] for r in lms_records if r['lms_payment_id']]
    duplicate_lms_ids = [id for id in set(lms_ids) if lms_ids.count(id) > 1]
    
    results['duplicate_lms_ids'] = len(duplicate_lms_ids)
    
    print(f"  LMS Payment IDs extracted: {len(lms_ids)}/{total_lms}")
    print(f"  Duplicate LMS Payment IDs: {len(duplicate_lms_ids)}")
    
    if duplicate_lms_ids:
        print(f"\n  Sample duplicate LMS IDs:")
        for lms_id in duplicate_lms_ids[:5]:
            matching = [r for r in lms_records if r['lms_payment_id'] == lms_id]
            print(f"    LMS ID {lms_id}: {len(matching)} occurrences")
            for m in matching[:2]:
                print(f"      Payment {m['payment_id']}: {m['payment_date']} ${m['amount']:.2f}")
    
    # 3. Charter linkage analysis
    print(f"\n3. Charter Linkage Analysis")
    print("-" * 60)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(charter_id) as has_charter_id,
            COUNT(reserve_number) as has_reserve_number,
            COUNT(client_id) as has_client_id
        FROM payments
        WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) = %s
        AND notes ILIKE '%%Imported from LMS%%'
    """, (year,))
    
    linkage = cur.fetchone()
    
    results['linkage'] = linkage
    
    print(f"  Total LMS imports: {linkage['total']}")
    print(f"  Linked to charter_id: {linkage['has_charter_id']} ({linkage['has_charter_id']/linkage['total']*100:.1f}%)")
    print(f"  Linked to reserve_number: {linkage['has_reserve_number']} ({linkage['has_reserve_number']/linkage['total']*100:.1f}%)")
    print(f"  Linked to client_id: {linkage['has_client_id']} ({linkage['has_client_id']/linkage['total']*100:.1f}%)")
    
    # 4. Check for negative amounts (refunds/corrections)
    print(f"\n4. Negative Amounts (Refunds/Corrections)")
    print("-" * 60)
    
    cur.execute("""
        SELECT 
            COUNT(*) as negative_count,
            SUM(amount) as negative_total,
            MIN(amount) as min_amount,
            MAX(amount) as max_amount
        FROM payments
        WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) = %s
        AND notes ILIKE '%%Imported from LMS%%'
        AND amount < 0
    """, (year,))
    
    negatives = cur.fetchone()
    
    results['negatives'] = negatives
    
    if negatives['negative_count'] > 0:
        print(f"  Negative payments: {negatives['negative_count']} (${negatives['negative_total']:,.2f})")
        print(f"  Range: ${negatives['min_amount']:.2f} to ${negatives['max_amount']:.2f}")
        
        # Sample negative payments
        cur.execute("""
            SELECT payment_id, payment_date, amount, reserve_number, notes
            FROM payments
            WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) = %s
            AND notes ILIKE '%%Imported from LMS%%'
            AND amount < 0
            ORDER BY amount
            LIMIT 5
        """, (year,))
        
        print(f"\n  Sample negative payments:")
        for row in cur.fetchall():
            print(f"    Payment {row['payment_id']}: ${row['amount']:.2f} (Reserve: {row['reserve_number']})")
    else:
        print(f"  No negative payments found")
    
    # 5. Check matching to charters that exist
    print(f"\n5. Charter Verification")
    print("-" * 60)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_with_reserve,
            COUNT(c.charter_id) as matched_charters,
            COUNT(CASE WHEN c.charter_id IS NULL THEN 1 END) as unmatched
        FROM payments p
        LEFT JOIN charters c ON p.reserve_number = c.reserve_number
        WHERE EXTRACT(YEAR FROM CAST(p.payment_date AS timestamp)) = %s
        AND p.notes ILIKE '%%Imported from LMS%%'
        AND p.reserve_number IS NOT NULL
    """, (year,))
    
    charter_check = cur.fetchone()
    
    results['charter_verification'] = charter_check
    
    print(f"  LMS payments with reserve_number: {charter_check['total_with_reserve']}")
    print(f"  Matched to existing charters: {charter_check['matched_charters']}")
    print(f"  Unmatched (orphaned): {charter_check['unmatched']}")
    
    if charter_check['unmatched'] > 0:
        print(f"\n  Sample orphaned payments:")
        cur.execute("""
            SELECT p.payment_id, p.payment_date, p.amount, p.reserve_number
            FROM payments p
            LEFT JOIN charters c ON p.reserve_number = c.reserve_number
            WHERE EXTRACT(YEAR FROM CAST(p.payment_date AS timestamp)) = %s
            AND p.notes ILIKE '%%Imported from LMS%%'
            AND p.reserve_number IS NOT NULL
            AND c.charter_id IS NULL
            LIMIT 5
        """, (year,))
        
        for row in cur.fetchall():
            print(f"    Payment {row['payment_id']}: ${row['amount']:.2f} (Reserve: {row['reserve_number']})")
    
    # 6. Comparison to total payments for the year
    print(f"\n6. LMS Import Percentage")
    print("-" * 60)
    
    cur.execute("""
        SELECT COUNT(*) as total_payments, SUM(amount) as total_amount
        FROM payments
        WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) = %s
    """, (year,))
    
    year_total = cur.fetchone()
    
    lms_pct = (total_lms / year_total['total_payments'] * 100) if year_total['total_payments'] > 0 else 0
    lms_amt_pct = (total_amount / year_total['total_amount'] * 100) if year_total['total_amount'] else 0
    
    results['year_total'] = year_total
    results['lms_percentage'] = lms_pct
    results['lms_amount_percentage'] = lms_amt_pct
    
    print(f"  Total payments in {year}: {year_total['total_payments']} (${year_total['total_amount']:,.2f})")
    print(f"  LMS imports: {total_lms} ({lms_pct:.1f}% of count)")
    print(f"  LMS amount: ${total_amount:,.2f} ({lms_amt_pct:.1f}% of total)")
    
    return results

def generate_summary(all_results):
    """Generate summary across all years."""
    print(f"\n{'='*80}")
    print(f"MULTI-YEAR LMS IMPORT SUMMARY (2013-2015)")
    print(f"{'='*80}\n")
    
    total_lms = sum(r['total_lms'] for r in all_results.values())
    total_amount = sum(r['total_amount'] for r in all_results.values())
    total_duplicates = sum(r['duplicate_lms_ids'] for r in all_results.values())
    
    print(f"Total LMS imports (2013-2015): {total_lms} payments (${total_amount:,.2f})")
    print(f"Duplicate LMS Payment IDs: {total_duplicates}")
    
    print(f"\nYear-by-Year Summary:")
    print("-" * 60)
    for year in sorted(all_results.keys()):
        r = all_results[year]
        print(f"\n{year}:")
        print(f"  Payments: {r['total_lms']} (${r['total_amount']:,.2f})")
        print(f"  Charter linkage: {r['linkage']['has_reserve_number']}/{r['total_lms']} ({r['linkage']['has_reserve_number']/r['total_lms']*100:.1f}%)")
        print(f"  Matched to charters: {r['charter_verification']['matched_charters']}/{r['charter_verification']['total_with_reserve']}")
        print(f"  Negative payments: {r['negatives']['negative_count']} (${r['negatives']['negative_total'] or 0:,.2f})")
        print(f"  LMS % of year: {r['lms_percentage']:.1f}% by count")
    
    # Calculate averages
    avg_charter_link = sum(r['linkage']['has_reserve_number']/r['total_lms']*100 for r in all_results.values()) / len(all_results)
    
    print(f"\nKEY METRICS:")
    print("-" * 60)
    print(f"  Average charter linkage: {avg_charter_link:.1f}%")
    print(f"  Total negative amounts: ${sum(r['negatives']['negative_total'] or 0 for r in all_results.values()):,.2f}")
    
    # Recommendations
    print(f"\nRECOMMENDATIONS:")
    print("-" * 60)
    
    if total_duplicates > 0:
        print(f"  1. Investigate {total_duplicates} duplicate LMS Payment IDs")
        print(f"     → May indicate re-imports or correction entries")
    
    orphaned_total = sum(r['charter_verification']['unmatched'] for r in all_results.values())
    if orphaned_total > 0:
        print(f"  2. Review {orphaned_total} orphaned payments (have reserve_number but no charter)")
        print(f"     → May be cancelled/deleted charters or data entry errors")
    
    negative_total = sum(r['negatives']['negative_count'] for r in all_results.values())
    if negative_total > 0:
        print(f"  3. Verify {negative_total} negative payments are legitimate refunds/corrections")
        print(f"     → Total: ${sum(r['negatives']['negative_total'] or 0 for r in all_results.values()):,.2f}")
    
    if avg_charter_link < 90:
        print(f"  4. Charter linkage at {avg_charter_link:.1f}% - consider matching improvements")
        print(f"     → Use reserve_number matching to improve linkage")

def main():
    """Main execution."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    years = [2013, 2014, 2015]
    all_results = {}
    
    try:
        for year in years:
            all_results[year] = audit_lms_year(cur, year)
        
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
