#!/usr/bin/env python
"""
Comprehensive payment matching analysis:
1. Find all possible matches for unmatched payments
2. Assess if existing matched payments are correct (causing credit overages)
3. Identify duplicate/mismatched applications

Strategy:
- Match by reserve_number
- Match by account_number + date proximity
- Match by amount + date proximity
- Check if overpaid charters have misapplied payments
"""
import psycopg2
from datetime import timedelta


def get_conn():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***",
    )


def main():
    conn = get_conn()
    cur = conn.cursor()

    print("=" * 100)
    print("PAYMENT MATCHING ANALYSIS & VERIFICATION")
    print("=" * 100)

    # 1. Find matchable unmatched payments by reserve_number
    print("\n1. UNMATCHED PAYMENTS MATCHABLE BY RESERVE_NUMBER")
    print("-" * 100)
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(COALESCE(p.payment_amount, p.amount, 0)),0)
        FROM payments p
        WHERE NOT EXISTS (
            SELECT 1 FROM charter_payments cp WHERE cp.payment_id = p.payment_id
        )
        AND p.reserve_number IS NOT NULL 
        AND p.reserve_number <> ''
        AND EXISTS (
            SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
        )
    """)
    matchable_reserve, matchable_reserve_sum = cur.fetchone()
    print(f"Matchable by reserve_number: {matchable_reserve:,} payments, ${float(matchable_reserve_sum):,.2f}")

    # 2. Find matchable by account_number
    print("\n2. UNMATCHED PAYMENTS MATCHABLE BY ACCOUNT_NUMBER")
    print("-" * 100)
    cur.execute("""
        SELECT COUNT(DISTINCT p.payment_id)
        FROM payments p
        WHERE NOT EXISTS (
            SELECT 1 FROM charter_payments cp WHERE cp.payment_id = p.payment_id
        )
        AND p.account_number IS NOT NULL 
        AND p.account_number <> ''
        AND p.payment_date IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM charters c 
            WHERE c.account_number = p.account_number
            AND c.charter_date IS NOT NULL
            AND ABS(EXTRACT(EPOCH FROM (c.charter_date::timestamp - p.payment_date::timestamp))/86400) <= 90
        )
    """)
    matchable_account = cur.fetchone()[0]
    print(f"Matchable by account_number (±90 days): {matchable_account:,} payments")

    # 3. Check for duplicate payment applications (same payment_id applied multiple times)
    print("\n3. DUPLICATE PAYMENT APPLICATIONS CHECK")
    print("-" * 100)
    cur.execute("""
        SELECT payment_id, COUNT(*) AS application_count, SUM(amount) AS total_applied
        FROM charter_payments
        WHERE payment_id IS NOT NULL
        GROUP BY payment_id
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
        LIMIT 10
    """)
    duplicates = cur.fetchall()
    if duplicates:
        print(f"Found {len(duplicates)} payments applied multiple times:")
        print(f"{'PaymentID':<12} {'Applications':<15} {'Total Applied':<15}")
        for pid, cnt, total in duplicates:
            print(f"{pid:<12} {cnt:<15} ${float(total):>13,.2f}")
    else:
        print("No duplicate applications found.")

    # 4. Verify overpaid charters - check if their payments are correct
    print("\n4. OVERPAID CHARTERS - PAYMENT VERIFICATION")
    print("-" * 100)
    cur.execute("""
        WITH overpaid AS (
            SELECT charter_id, reserve_number, 
                   COALESCE(total_amount_due,0) AS total_due,
                   COALESCE(paid_amount,0) AS paid
            FROM charters
            WHERE COALESCE(paid_amount,0) > COALESCE(total_amount_due,0) + 0.01
            ORDER BY (paid_amount - total_amount_due) DESC
            LIMIT 50
        ),
        payment_counts AS (
            SELECT cp.charter_id, COUNT(*) AS payment_count, SUM(cp.amount) AS cp_sum
            FROM charter_payments cp
            GROUP BY cp.charter_id
        )
        SELECT o.charter_id, o.reserve_number, o.total_due, o.paid,
               COALESCE(pc.payment_count, 0) AS payment_count,
               COALESCE(pc.cp_sum, 0) AS charter_payments_sum,
               (o.paid - o.total_due) AS overpayment
        FROM overpaid o
        LEFT JOIN payment_counts pc ON pc.charter_id = o.reserve_number::text
        ORDER BY overpayment DESC
        LIMIT 10
    """)
    print(f"{'Charter':<8} {'Reserve':<8} {'Due':<12} {'Paid':<12} {'PayCnt':<8} {'CP_Sum':<12} {'Overpay':<12}")
    for row in cur.fetchall():
        print(f"{row[0]:<8} {row[1]:<8} ${float(row[2]):>10,.2f} ${float(row[3]):>10,.2f} "
              f"{row[4]:<8} ${float(row[5]):>10,.2f} ${float(row[6]):>10,.2f}")

    # 5. Check if charter_payments sum matches charters.paid_amount for overpaid
    print("\n5. CHARTER_PAYMENTS SUM VS PAID_AMOUNT DISCREPANCY (Overpaid Charters)")
    print("-" * 100)
    cur.execute("""
        WITH overpaid AS (
            SELECT charter_id, reserve_number, 
                   COALESCE(paid_amount,0) AS paid
            FROM charters
            WHERE COALESCE(paid_amount,0) > COALESCE(total_amount_due,0) + 0.01
            LIMIT 100
        ),
        payment_sums AS (
            SELECT cp.charter_id, SUM(cp.amount) AS cp_sum
            FROM charter_payments cp
            GROUP BY cp.charter_id
        )
        SELECT 
            COUNT(*) AS overpaid_count,
            COUNT(*) FILTER(WHERE ABS(o.paid - COALESCE(ps.cp_sum,0)) > 0.02) AS mismatch_count
        FROM overpaid o
        LEFT JOIN payment_sums ps ON ps.charter_id = o.reserve_number::text
    """)
    overpaid_count, mismatch_count = cur.fetchone()
    print(f"Top 100 overpaid charters analyzed:")
    print(f"  Paid_amount ≠ charter_payments sum: {mismatch_count} ({100*mismatch_count/overpaid_count:.1f}%)")

    # 6. Sample overpaid charters with payment detail
    print("\n6. SAMPLE OVERPAID CHARTER PAYMENT DETAILS")
    print("-" * 100)
    cur.execute("""
        SELECT c.charter_id, c.reserve_number, c.total_amount_due, c.paid_amount
        FROM charters c
        WHERE COALESCE(c.paid_amount,0) > COALESCE(c.total_amount_due,0) + 0.01
        ORDER BY (c.paid_amount - c.total_amount_due) DESC
        LIMIT 3
    """)
    samples = cur.fetchall()
    for charter_id, reserve_num, total_due, paid in samples:
        total_due = float(total_due) if total_due is not None else 0.0
        paid = float(paid) if paid is not None else 0.0
        print(f"\nCharter {charter_id} (Reserve {reserve_num}): Due=${total_due:.2f}, Paid=${paid:.2f}")
        cur.execute("""
            SELECT cp.payment_id, cp.amount, cp.payment_date, cp.payment_method, 
                   p.account_number, p.reserve_number AS p_reserve
            FROM charter_payments cp
            LEFT JOIN payments p ON p.payment_id = cp.payment_id
            WHERE cp.charter_id = %s
            ORDER BY cp.payment_date
        """, (reserve_num,))
        cp_rows = cur.fetchall()
        if cp_rows:
            print(f"  Payments applied ({len(cp_rows)}):")
            for cp_row in cp_rows:
                p_reserve = cp_row[5] if cp_row[5] else 'NULL'
                match_status = '✓' if p_reserve == reserve_num else ('?' if p_reserve == 'NULL' else f'✗ ({p_reserve})')
                print(f"    PID {cp_row[0]}: ${float(cp_row[1]):.2f} on {cp_row[2]} via {cp_row[3]} | reserve={p_reserve} {match_status}")
        else:
            print(f"  No charter_payments found!")

    # 7. Check for payments applied to wrong charter (reserve_number mismatch)
    print("\n7. MISMATCHED PAYMENTS (Applied to wrong charter)")
    print("-" * 100)
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(cp.amount),0)
        FROM charter_payments cp
        JOIN payments p ON p.payment_id = cp.payment_id
        WHERE p.reserve_number IS NOT NULL 
        AND p.reserve_number <> ''
        AND cp.charter_id <> p.reserve_number
    """)
    mismatched_count, mismatched_sum = cur.fetchone()
    print(f"Payments applied to different charter than reserve_number indicates:")
    print(f"  Count: {mismatched_count:,}")
    print(f"  Amount: ${float(mismatched_sum):,.2f}")

    if mismatched_count > 0:
        print("\n  Sample mismatches (first 10):")
        cur.execute("""
            SELECT cp.payment_id, cp.charter_id AS applied_to, p.reserve_number AS payment_reserve,
                   cp.amount, cp.payment_date
            FROM charter_payments cp
            JOIN payments p ON p.payment_id = cp.payment_id
            WHERE p.reserve_number IS NOT NULL 
            AND p.reserve_number <> ''
            AND cp.charter_id <> p.reserve_number
            ORDER BY cp.amount DESC
            LIMIT 10
        """)
        print(f"  {'PayID':<8} {'Applied To':<12} {'Should Be':<12} {'Amount':<12} {'Date':<12}")
        for row in cur.fetchall():
            print(f"  {row[0]:<8} {row[1]:<12} {row[2]:<12} ${float(row[3]):>10,.2f} {str(row[4]):<12}")

    print("\n" + "=" * 100)
    print("SUMMARY & RECOMMENDATIONS")
    print("=" * 100)
    print(f"1. Can auto-match {matchable_reserve:,} payments by reserve_number (${float(matchable_reserve_sum):,.2f})")
    print(f"2. {mismatched_count:,} payments may be applied to wrong charters (${float(mismatched_sum):,.2f})")
    print(f"3. {mismatch_count} of top 100 overpaid charters show paid_amount ≠ charter_payments sum")
    print("\nNext steps:")
    print("  - Fix mismatched payments (move to correct charter)")
    print("  - Apply the matchable unmatched payments")
    print("  - Re-sync paid_amount after corrections")
    print("=" * 100)

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
