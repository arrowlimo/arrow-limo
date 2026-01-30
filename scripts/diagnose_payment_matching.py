#!/usr/bin/env python
"""
Deep dive into payment matching issues:
1. Check charter_payments structure and linkage method
2. Verify reserve_number vs charter_id usage
3. Sample unmatched payments to identify patterns
4. Compare payments vs charter_payments counts and amounts
"""
import psycopg2


def get_conn():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***",
    )


def main():
    conn = get_conn()
    cur = conn.cursor()

    print("=" * 80)
    print("PAYMENT MATCHING DIAGNOSIS")
    print("=" * 80)

    # 1. charter_payments structure
    print("\n1. CHARTER_PAYMENTS TABLE STRUCTURE")
    print("-" * 80)
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name='charter_payments'
        ORDER BY ordinal_position
    """)
    print("Columns:")
    for col, dtype in cur.fetchall():
        print(f"  {col}: {dtype}")

    # 2. Count and sum charter_payments
    cur.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM charter_payments")
    cp_count, cp_sum = cur.fetchone()
    print(f"\nTotal charter_payments records: {cp_count:,}")
    print(f"Total charter_payments amount: ${float(cp_sum):,.2f}")

    # 3. How many charter_payments have payment_id?
    cur.execute("SELECT COUNT(*) FROM charter_payments WHERE payment_id IS NOT NULL")
    cp_with_payment_id = cur.fetchone()[0]
    print(f"charter_payments with payment_id: {cp_with_payment_id:,} ({100*cp_with_payment_id/cp_count:.1f}%)")

    # 4. Compare linkage: charter_payments.charter_id field type
    cur.execute("""
        SELECT data_type FROM information_schema.columns 
        WHERE table_name='charter_payments' AND column_name='charter_id'
    """)
    cp_charter_id_type = cur.fetchone()
    print(f"charter_payments.charter_id type: {cp_charter_id_type[0] if cp_charter_id_type else 'MISSING'}")

    # 5. Sample charter_payments to see actual data
    print("\n2. CHARTER_PAYMENTS SAMPLE (first 5 rows)")
    print("-" * 80)
    cur.execute("""
        SELECT charter_id, payment_id, amount, payment_date, payment_method
        FROM charter_payments
        LIMIT 5
    """)
    for row in cur.fetchall():
        print(f"  charter_id={row[0]}, payment_id={row[1]}, amount=${float(row[2]):.2f}, date={row[3]}, method={row[4]}")

    # 6. Verify charter_payments.charter_id matches charters.reserve_number (text) not charter_id (int)
    print("\n3. CHARTER_PAYMENTS LINKAGE VERIFICATION")
    print("-" * 80)
    cur.execute("""
        SELECT COUNT(*) 
        FROM charter_payments cp
        JOIN charters c ON c.reserve_number = cp.charter_id::text
    """)
    matched_by_reserve = cur.fetchone()[0]
    print(f"charter_payments matched via reserve_number: {matched_by_reserve:,} ({100*matched_by_reserve/cp_count:.1f}%)")

    cur.execute("""
        SELECT COUNT(*) 
        FROM charter_payments cp
        WHERE NOT EXISTS (
            SELECT 1 FROM charters c WHERE c.reserve_number = cp.charter_id::text
        )
    """)
    orphaned_cp = cur.fetchone()[0]
    print(f"charter_payments orphaned (no charter match): {orphaned_cp:,}")

    # 7. Sample unmatched payments (no charter_payments link)
    print("\n4. SAMPLE UNMATCHED PAYMENTS (first 10)")
    print("-" * 80)
    cur.execute("""
        SELECT p.payment_id, p.reserve_number, p.account_number, 
               COALESCE(p.payment_amount, p.amount) AS amt,
               p.payment_method, p.payment_date
        FROM payments p
        WHERE NOT EXISTS (
            SELECT 1 FROM charter_payments cp WHERE cp.payment_id = p.payment_id
        )
        AND COALESCE(p.payment_amount, p.amount, 0) > 0
        ORDER BY COALESCE(p.payment_amount, p.amount, 0) DESC
        LIMIT 10
    """)
    print(f"{'PaymentID':<12} {'Reserve':<10} {'Account':<10} {'Amount':<12} {'Method':<15} {'Date':<12}")
    for row in cur.fetchall():
        amt = float(row[3]) if row[3] else 0
        print(f"{row[0]:<12} {str(row[1] or ''):<10} {str(row[2] or ''):<10} ${amt:>10,.2f} {str(row[4] or ''):<15} {str(row[5]):<12}")

    # 8. Check if unmatched payments have reserve_number that could be matched
    print("\n5. UNMATCHED PAYMENTS WITH RESERVE_NUMBER")
    print("-" * 80)
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(COALESCE(payment_amount, amount, 0)),0)
        FROM payments p
        WHERE NOT EXISTS (
            SELECT 1 FROM charter_payments cp WHERE cp.payment_id = p.payment_id
        )
        AND p.reserve_number IS NOT NULL AND p.reserve_number <> ''
    """)
    unmatched_with_reserve, unmatched_reserve_sum = cur.fetchone()
    print(f"Unmatched payments WITH reserve_number: {unmatched_with_reserve:,}")
    print(f"Amount: ${float(unmatched_reserve_sum):,.2f}")

    # 9. Check if those reserve numbers exist in charters
    cur.execute("""
        SELECT COUNT(*)
        FROM payments p
        WHERE NOT EXISTS (
            SELECT 1 FROM charter_payments cp WHERE cp.payment_id = p.payment_id
        )
        AND p.reserve_number IS NOT NULL AND p.reserve_number <> ''
        AND EXISTS (
            SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
        )
    """)
    matchable_by_reserve = cur.fetchone()[0]
    print(f"  Of those, matchable to existing charters: {matchable_by_reserve:,}")

    print("\n" + "=" * 80)
    print("DIAGNOSIS:")
    print("-" * 80)
    print("Issue: charter_payments.payment_id linkage may be incomplete.")
    print("Likely causes:")
    print("  1. Payments imported but not yet applied to charter_payments")
    print("  2. Missing migration step: payments → charter_payments creation")
    print("  3. Different payment sources (Square, QBO) not fully integrated")
    print(f"\nActionable: {matchable_by_reserve:,} unmatched payments have valid reserve_numbers")
    print("  → Can be auto-matched and inserted into charter_payments")
    print("=" * 80)

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
