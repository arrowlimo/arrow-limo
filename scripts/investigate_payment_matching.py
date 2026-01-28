#!/usr/bin/env python3
"""
Investigate payment matching discrepancy.
Compare current count vs previous analysis.
"""

import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***"
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("PAYMENT MATCHING INVESTIGATION")
    print("=" * 100)
    print()
    
    # Total payments 2007-2024
    cur.execute("""
        SELECT COUNT(*), SUM(COALESCE(amount, 0))
        FROM payments
        WHERE EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
    """)
    
    total_count, total_amount = cur.fetchone()
    print(f"TOTAL PAYMENTS (2007-2024): {total_count:,}")
    print(f"Total amount: ${float(total_amount):,.2f}")
    print()
    
    # Matched payments (charter_id IS NOT NULL AND charter_id != 0)
    cur.execute("""
        SELECT COUNT(*), SUM(COALESCE(amount, 0))
        FROM payments
        WHERE EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
        AND charter_id IS NOT NULL
        AND charter_id != 0
    """)
    
    matched_count, matched_amount = cur.fetchone()
    matched_pct = 100 * matched_count / total_count if total_count > 0 else 0
    print(f"MATCHED PAYMENTS (charter_id IS NOT NULL AND != 0): {matched_count:,}")
    print(f"Matched amount: ${float(matched_amount):,.2f}")
    print(f"Match rate: {matched_pct:.2f}%")
    print()
    
    # Unmatched (charter_id IS NULL OR charter_id = 0)
    cur.execute("""
        SELECT COUNT(*), SUM(COALESCE(amount, 0))
        FROM payments
        WHERE EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
        AND (charter_id IS NULL OR charter_id = 0)
    """)
    
    unmatched_count, unmatched_amount = cur.fetchone()
    unmatched_pct = 100 * unmatched_count / total_count if total_count > 0 else 0
    print(f"UNMATCHED PAYMENTS (charter_id IS NULL OR = 0): {unmatched_count:,}")
    print(f"Unmatched amount: ${float(unmatched_amount):,.2f}")
    print(f"Unmatch rate: {unmatched_pct:.2f}%")
    print()
    
    # Check if there are payments with charter_id = 0 specifically
    cur.execute("""
        SELECT COUNT(*)
        FROM payments
        WHERE EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
        AND charter_id = 0
    """)
    
    zero_count = cur.fetchone()[0]
    print(f"Payments with charter_id = 0 (explicitly zero): {zero_count:,}")
    
    # Check if there are payments with charter_id IS NULL
    cur.execute("""
        SELECT COUNT(*)
        FROM payments
        WHERE EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
        AND charter_id IS NULL
    """)
    
    null_count = cur.fetchone()[0]
    print(f"Payments with charter_id IS NULL: {null_count:,}")
    print()
    
    # Verify totals add up
    print("=" * 100)
    print("VERIFICATION:")
    print("=" * 100)
    print()
    print(f"Matched: {matched_count:,}")
    print(f"Unmatched (NULL): {null_count:,}")
    print(f"Unmatched (= 0): {zero_count:,}")
    print(f"Total unmatched: {unmatched_count:,}")
    print(f"Sum: {matched_count + unmatched_count:,}")
    print(f"Expected total: {total_count:,}")
    
    if matched_count + unmatched_count == total_count:
        print("[OK] Counts match!")
    else:
        print(f"[FAIL] Discrepancy: {total_count - (matched_count + unmatched_count):,}")
    
    print()
    
    # Check previous analysis result (from earlier session)
    print("=" * 100)
    print("COMPARISON TO PREVIOUS ANALYSIS:")
    print("=" * 100)
    print()
    
    # Previous result from analyze_charter_payment_status.py showed:
    # Total: 50,504 payments
    # Matched: 39,124 (77.5%)
    # Unmatched: 11,380 (22.5%)
    
    print("Previous analysis (from analyze_charter_payment_status.py):")
    print(f"  Total: 50,504 payments")
    print(f"  Matched: 39,124 (77.5%)")
    print(f"  Unmatched: 11,380 (22.5%)")
    print()
    
    print("Current analysis:")
    print(f"  Total: {total_count:,} payments")
    print(f"  Matched: {matched_count:,} ({matched_pct:.2f}%)")
    print(f"  Unmatched: {unmatched_count:,} ({unmatched_pct:.2f}%)")
    print()
    
    if abs(total_count - 50504) < 100:
        print("[OK] Totals are consistent")
    else:
        print(f"[WARN] Total count difference: {total_count - 50504:,}")
    
    if abs(unmatched_count - 11380) < 100:
        print("[OK] Unmatched counts are consistent")
    else:
        print(f"[WARN] Unmatched count difference: {unmatched_count - 11380:,}")
    
    print()
    print("NOTE: If you were expecting 98% match rate, that might be from a different")
    print("      analysis (possibly Square payments, or a specific subset of data).")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
