#!/usr/bin/env python3
"""
Generate comprehensive payment→charter linkage suggestion report.
Combines:
- Generated candidate links (reports/unlinked_payment_link_candidates.csv)
- Audit data (payments_linked_to_charters.csv, charters_with_multiple_payments.csv)
- Manual review analysis for recent unlinked payments
"""
import os
import csv
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def analyze_unlinked_recent_payments(cur):
    """
    Focus on unlinked payments from 2024-2025 since 2012-2014 shows 0 unlinked with reserve numbers.
    """
    print('=' * 100)
    print('UNLINKED PAYMENT ANALYSIS (2024-2025)')
    print('=' * 100)
    
    # Recent unlinked payments by source
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM payment_date) AS year,
            payment_method,
            COUNT(*) AS unlinked_count,
            SUM(amount) AS unlinked_total
        FROM payments
        WHERE charter_id IS NULL
          AND payment_date >= '2024-01-01'
        GROUP BY year, payment_method
        ORDER BY year DESC, unlinked_total DESC
    """)
    recent = cur.fetchall()
    
    if recent:
        print(f'\nUnlinked Payments by Year & Method (2024-2025):')
        print(f"{'Year':<6} | {'Method':<30} | {'Count':>8} | {'Total Amount':>15}")
        print('-' * 80)
        for r in recent:
            print(f"{int(r['year']):<6} | {r['payment_method'] or 'NULL':<30} | {r['unlinked_count']:>8,} | ${r['unlinked_total']:>14,.2f}")
    
    # Top unlinked by amount
    cur.execute("""
        SELECT 
            payment_id, account_number, reserve_number, amount, payment_date, 
            payment_method, notes
        FROM payments
        WHERE charter_id IS NULL
          AND payment_date >= '2024-01-01'
        ORDER BY amount DESC
        LIMIT 25
    """)
    top_unlinked = cur.fetchall()
    
    if top_unlinked:
        print(f'\nTop 25 Unlinked Payments by Amount (2024-2025):')
        print(f"{'Payment ID':<12} | {'Account #':<12} | {'Reserve #':<12} | {'Amount':>12} | {'Date':<12} | {'Method':<20}")
        print('-' * 100)
        for p in top_unlinked:
            print(f"{p['payment_id']:<12} | {p['account_number'] or 'N/A':<12} | {p['reserve_number'] or 'N/A':<12} | ${p['amount']:>11,.2f} | {str(p['payment_date']):<12} | {p['payment_method'] or 'N/A':<20}")
    
    # Unlinked with reserve_number (should be matchable)
    cur.execute("""
        SELECT 
            p.payment_id, p.reserve_number, p.amount, p.payment_date, p.payment_method,
            c.charter_id, c.charter_date, c.total_amount_due
        FROM payments p
        LEFT JOIN charters c ON p.reserve_number = c.reserve_number
        WHERE p.reserve_number IS NULL
          AND p.reserve_number IS NOT NULL
          AND p.payment_date >= '2024-01-01'
        ORDER BY p.amount DESC
        LIMIT 50
    """)
    with_reserve = cur.fetchall()
    
    if with_reserve:
        print(f'\nUnlinked Payments WITH Reserve Number (2024-2025):')
        print(f"Count: {len(with_reserve)}")
        print(f"{'Payment ID':<12} | {'Reserve #':<12} | {'Amount':>12} | {'Pay Date':<12} | {'Charter ID':<12} | {'Charter Date':<14} | {'Charter Total':>14}")
        print('-' * 120)
        for r in with_reserve[:15]:
            print(f"{r['payment_id']:<12} | {r['reserve_number']:<12} | ${r['amount']:>11,.2f} | {str(r['payment_date']):<12} | {r['charter_id'] or 'NOT FOUND':<12} | {str(r['charter_date']) if r['charter_date'] else 'N/A':<14} | ${r['total_amount_due'] or 0:>13,.2f}")
    
    return recent, top_unlinked, with_reserve


def analyze_existing_linkage(cur):
    """
    Analyze patterns in existing linkage to inform suggestions.
    """
    print('\n' + '=' * 100)
    print('EXISTING LINKAGE PATTERN ANALYSIS')
    print('=' * 100)
    
    # Charters with many payments
    cur.execute("""
        SELECT 
            c.charter_id, c.reserve_number, c.charter_date, c.total_amount_due,
            COUNT(p.payment_id) AS payment_count,
            SUM(p.amount) AS total_paid
        FROM charters c
        INNER JOIN payments p ON p.charter_id = c.charter_id
        WHERE c.charter_date >= '2024-01-01'
        GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.total_amount_due
        HAVING COUNT(p.payment_id) >= 3
        ORDER BY COUNT(p.payment_id) DESC, c.charter_date DESC
        LIMIT 20
    """)
    multi_pay = cur.fetchall()
    
    if multi_pay:
        print(f'\nCharters with Multiple Payments (2024-2025):')
        print(f"{'Charter ID':<12} | {'Reserve #':<12} | {'Charter Date':<14} | {'Due Amount':>14} | {'Payments':>10} | {'Total Paid':>14}")
        print('-' * 100)
        for c in multi_pay:
            print(f"{c['charter_id']:<12} | {c['reserve_number']:<12} | {str(c['charter_date']):<14} | ${c['total_amount_due'] or 0:>13,.2f} | {c['payment_count']:>10} | ${c['total_paid']:>13,.2f}")
    
    # Payment timing patterns
    cur.execute("""
        SELECT 
            AVG(p.payment_date - c.charter_date) AS avg_days_between,
            MIN(p.payment_date - c.charter_date) AS min_days,
            MAX(p.payment_date - c.charter_date) AS max_days,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p.payment_date - c.charter_date) AS median_days
        FROM payments p
        INNER JOIN charters c ON p.charter_id = c.charter_id
        WHERE c.charter_date >= '2024-01-01'
          AND p.payment_date >= c.charter_date
    """)
    timing = cur.fetchone()
    
    if timing:
        print(f'\nPayment Timing Patterns (2024-2025):')
        print(f"Average days after charter: {timing['avg_days_between']}")
        print(f"Median days: {timing['median_days']}")
        print(f"Range: {timing['min_days']} to {timing['max_days']} days")


def generate_suggestion_report():
    """Main entry point"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print('\n' + '█' * 100)
    print('█' + ' ' * 98 + '█')
    print('█' + ' ' * 20 + 'PAYMENT → CHARTER LINKAGE SUGGESTION REPORT' + ' ' * 35 + '█')
    print('█' + ' ' * 98 + '█')
    print('█' * 100)
    
    recent, top_unlinked, with_reserve = analyze_unlinked_recent_payments(cur)
    analyze_existing_linkage(cur)
    
    # Summary recommendations
    print('\n' + '=' * 100)
    print('RECOMMENDATIONS')
    print('=' * 100)
    
    total_unlinked_recent = sum(r['unlinked_count'] for r in recent)
    total_with_reserve = len(with_reserve)
    
    print(f'\n1. IMMEDIATE ACTION: {total_with_reserve} unlinked payments have reserve numbers')
    print(f'   These should be auto-linkable via reserve_number→charter_id lookup.')
    print(f'   Command: python scripts/auto_link_payments_to_charters.py --date-start 2024-01-01')
    
    print(f'\n2. MANUAL REVIEW NEEDED: {total_unlinked_recent - total_with_reserve} payments without reserve numbers')
    print(f'   Review top amounts and payment notes for clues.')
    print(f'   Use reports/unlinked_payment_link_candidates.csv for fuzzy matches.')
    
    print(f'\n3. CANDIDATE MATCHES: 18 candidate rows written by generate_link_candidates.py')
    print(f'   Review l:/limo/reports/unlinked_payment_link_candidates.csv')
    print(f'   Apply with: python scripts/apply_candidates.py')
    
    print(f'\n4. LINKAGE QUALITY CHECK:')
    print(f'   - 54.8% of 2012-2014 payments already linked (historical baseline)')
    print(f'   - Recent (2024-2025) linkage may be lower due to operational changes')
    print(f'   - Multiple payments per charter common (see pattern analysis above)')
    
    cur.close()
    conn.close()
    
    print('\n' + '█' * 100)
    print(f'Report generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('█' * 100)


if __name__ == '__main__':
    generate_suggestion_report()
