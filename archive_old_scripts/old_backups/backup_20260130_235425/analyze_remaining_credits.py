#!/usr/bin/env python
"""
Analyze remaining negative balances after payment matching fix.
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
    print("REMAINING NEGATIVE BALANCES ANALYSIS")
    print("=" * 80)
    
    # Get top negative balances
    print("\nTop 20 charters with largest credits:")
    cur.execute("""
        SELECT c.reserve_number, c.charter_date, 
               COALESCE(c.total_amount_due, 0) AS total_due,
               COALESCE(c.paid_amount, 0) AS paid,
               c.balance,
               (SELECT COUNT(*) FROM charter_payments cp WHERE cp.charter_id = c.reserve_number::text) AS payment_count,
               c.status, c.cancelled
        FROM charters c
        WHERE c.balance < -0.01
        AND (c.cancelled IS NULL OR c.cancelled = FALSE)
        ORDER BY c.balance ASC
        LIMIT 20
    """)
    
    for row in cur.fetchall():
        reserve, date, total, paid, balance, pay_cnt, status, cancelled = row
        print(f"\n  {reserve} ({date})")
        print(f"    Total due: ${float(total):,.2f}")
        print(f"    Paid: ${float(paid):,.2f}")
        print(f"    Balance: ${float(balance):,.2f}")
        print(f"    Payments linked: {pay_cnt}")
        print(f"    Status: {status}, Cancelled: {cancelled}")
    
    # Check if these have refunds
    print("\n" + "=" * 80)
    print("CREDITS WITH REFUNDS")
    print("=" * 80)
    
    cur.execute("""
        SELECT COUNT(*) AS with_refunds,
               COALESCE(SUM(c.balance), 0) AS balance_sum
        FROM charters c
        WHERE c.balance < -0.01
        AND (c.cancelled IS NULL OR c.cancelled = FALSE)
        AND EXISTS (
            SELECT 1 FROM charter_refunds cr 
            WHERE cr.charter_id::text = c.reserve_number::text
        )
    """)
    with_refunds, refund_balance = cur.fetchone()
    
    cur.execute("""
        SELECT COUNT(*) AS without_refunds,
               COALESCE(SUM(c.balance), 0) AS balance_sum
        FROM charters c
        WHERE c.balance < -0.01
        AND (c.cancelled IS NULL OR c.cancelled = FALSE)
        AND NOT EXISTS (
            SELECT 1 FROM charter_refunds cr 
            WHERE cr.charter_id::text = c.reserve_number::text
        )
    """)
    without_refunds, no_refund_balance = cur.fetchone()
    
    print(f"\nWith refunds: {with_refunds:,} (${float(refund_balance):,.2f})")
    print(f"Without refunds: {without_refunds:,} (${float(no_refund_balance):,.2f})")
    
    # Check cancelled status distribution
    print("\n" + "=" * 80)
    print("CANCELLED STATUS CHECK")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            CASE 
                WHEN cancelled = TRUE THEN 'Cancelled=TRUE'
                WHEN booking_status = 'cancelled' THEN 'booking_status=cancelled'
                WHEN status = 'cancelled' THEN 'status=cancelled'
                ELSE 'Not cancelled'
            END AS cancel_type,
            COUNT(*) AS count,
            COALESCE(SUM(balance), 0) AS balance_sum
        FROM charters
        WHERE balance < -0.01
        GROUP BY cancel_type
        ORDER BY count DESC
    """)
    
    for row in cur.fetchall():
        cancel_type, count, balance = row
        print(f"  {cancel_type}: {count:,} (${float(balance):,.2f})")
    
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
