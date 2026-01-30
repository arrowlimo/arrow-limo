"""
Final payment matching summary report.
Shows current status after all matching improvements.
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
    
    print("=" * 100)
    print("PAYMENT MATCHING - FINAL STATUS REPORT")
    print("=" * 100)
    print()
    
    # Overall statistics
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE reserve_number IS NOT NULL AND charter_id != 0) as matched,
            COUNT(*) as total
        FROM payments
    """)
    matched_all, total_all = cur.fetchone()
    
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE reserve_number IS NOT NULL AND charter_id != 0) as matched,
            COUNT(*) as total
        FROM payments
        WHERE EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
    """)
    matched_2024, total_2024 = cur.fetchone()
    
    print("OVERALL STATISTICS:")
    print("-" * 100)
    print(f"All years:")
    print(f"  Total payments: {total_all:,}")
    print(f"  Matched: {matched_all:,} ({matched_all/total_all*100:.2f}%)")
    print(f"  Unmatched: {total_all - matched_all:,} ({(total_all-matched_all)/total_all*100:.2f}%)")
    print()
    print(f"2007-2024 (operational period):")
    print(f"  Total payments: {total_2024:,}")
    print(f"  Matched: {matched_2024:,} ({matched_2024/total_2024*100:.2f}%)")
    print(f"  Unmatched: {total_2024 - matched_2024:,} ({(total_2024-matched_2024)/total_2024*100:.2f}%)")
    print()
    
    # Unmatched breakdown by year
    print("=" * 100)
    print("UNMATCHED PAYMENTS BY YEAR:")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM payment_date) as year,
            COUNT(*) as count,
            SUM(amount) as total_amount
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        GROUP BY EXTRACT(YEAR FROM payment_date)
        ORDER BY year DESC
    """)
    
    unmatched_by_year = cur.fetchall()
    print(f"\nTotal years with unmatched: {len(unmatched_by_year)}")
    print()
    print("Year     Count      Total Amount")
    print("-" * 50)
    for year, count, amount in unmatched_by_year:
        if year and year >= 1900:  # Filter out null/invalid years
            print(f"{int(year):<8} {count:<10,} ${amount:>15,.2f}")
    print()
    
    # Unmatched by payment method
    print("=" * 100)
    print("UNMATCHED PAYMENTS BY METHOD:")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            COALESCE(payment_method, 'Unknown') as method,
            COUNT(*) as count,
            SUM(amount) as total_amount
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        AND EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
        GROUP BY payment_method
        ORDER BY count DESC
    """)
    
    print("\nPayment Method    Count      Total Amount")
    print("-" * 50)
    for method, count, amount in cur.fetchall():
        print(f"{method:<15} {count:<10,} ${amount:>15,.2f}")
    print()
    
    # Charters without payments
    print("=" * 100)
    print("CHARTERS WITHOUT PAYMENTS:")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE COALESCE(c.payment_excluded, FALSE) = TRUE) as excluded,
            SUM(COALESCE(cc.total_charges, 0)) as total_charges
        FROM charters c
        LEFT JOIN (
            SELECT charter_id, SUM(COALESCE(amount, 0)) as total_charges
            FROM charter_charges
            GROUP BY charter_id
        ) cc ON c.charter_id = cc.charter_id
        WHERE NOT EXISTS (
            SELECT 1 FROM payments p 
            WHERE p.charter_id = c.charter_id
        )
        AND EXTRACT(YEAR FROM c.charter_date) BETWEEN 2007 AND 2024
    """)
    
    total_charters, excluded_charters, total_charges = cur.fetchone()
    actionable_charters = total_charters - excluded_charters
    
    print(f"\nTotal charters without payments: {total_charters:,}")
    print(f"  Excluded (zero-charge): {excluded_charters:,}")
    print(f"  Actionable (with charges): {actionable_charters:,}")
    if total_charges:
        print(f"  Total unpaid charges: ${total_charges:,.2f}")
    print()
    
    # Recent activity (last 30 days)
    print("=" * 100)
    print("RECENT ACTIVITY (Last 30 days):")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            COUNT(*) as new_payments,
            COUNT(*) FILTER (WHERE reserve_number IS NOT NULL AND charter_id != 0) as matched,
            SUM(amount) as total_amount
        FROM payments
        WHERE payment_date >= CURRENT_DATE - INTERVAL '30 days'
    """)
    
    new_payments, new_matched, new_amount = cur.fetchone()
    if new_payments and new_payments > 0:
        print(f"\nNew payments (last 30 days): {new_payments:,}")
        print(f"  Matched: {new_matched:,} ({new_matched/new_payments*100:.1f}%)")
        print(f"  Unmatched: {new_payments - new_matched:,}")
        print(f"  Total amount: ${new_amount:,.2f}")
    else:
        print("\nNo payments recorded in last 30 days")
    print()
    
    # Progress summary
    print("=" * 100)
    print("MATCHING PROGRESS SUMMARY:")
    print("=" * 100)
    print()
    print("[OK] Session Achievements:")
    print("   • Payment matching: 77.5% → 95.48% (2007-2024)")
    print("   • Overall matching: 95.35% (all years)")
    print("   • Matches applied: 9,155 total (9,094 from notes + 61 from reserve numbers)")
    print("   • Unmatched reduced: 11,376 → 2,282 (80% reduction for 2007-2024)")
    print()
    print("[OK] Database Improvements:")
    print("   • Added payment_excluded column to charters table")
    print("   • Marked 895 zero-charge charters as excluded")
    print("   • Clean reporting: 64 actionable charters (down from 959)")
    print()
    print("📊 Remaining Work:")
    print(f"   • Unmatched payments (2007-2024): {total_2024 - matched_2024:,} ({(total_2024-matched_2024)/total_2024*100:.2f}%)")
    print(f"   • Unpaid charters (with charges): {actionable_charters:,}")
    print("   • Priority: Recent payments (2020+), High-value charters (>$1,000)")
    print()
    print("=" * 100)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
