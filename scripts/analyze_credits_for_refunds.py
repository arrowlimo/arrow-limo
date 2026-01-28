#!/usr/bin/env python
"""
Analyze credits to identify which need refunds processed.
Compares charter credits against charter_refunds table.
"""
import psycopg2


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
    
    print("=" * 80)
    print("CREDIT ANALYSIS FOR REFUND PROCESSING")
    print("=" * 80)
    
    # Get credits without refunds
    cur.execute("""
        SELECT c.charter_id, c.reserve_number, c.charter_date,
               c.total_amount_due, c.paid_amount, c.balance,
               c.status, c.cancelled,
               (SELECT COUNT(*) FROM charter_payments cp 
                WHERE cp.charter_id = c.reserve_number::text) AS payment_count
        FROM charters c
        WHERE c.balance < -0.01
        AND (c.cancelled IS NULL OR c.cancelled = FALSE)
        AND NOT EXISTS (
            SELECT 1 FROM charter_refunds cr 
            WHERE cr.charter_id::text = c.reserve_number::text
        )
        ORDER BY c.balance ASC
    """)
    
    credits_no_refund = cur.fetchall()
    total_credits_amount = sum(float(row[5]) for row in credits_no_refund)
    
    print(f"\nCredits without documented refunds: {len(credits_no_refund):,}")
    print(f"Total credit amount: ${float(total_credits_amount):,.2f}")
    
    # Categorize by magnitude
    small_credits = []  # < $50
    medium_credits = []  # $50-$500
    large_credits = []  # $500-$2000
    very_large_credits = []  # > $2000
    
    for row in credits_no_refund:
        balance = float(row[5])
        if balance > -50:
            small_credits.append(row)
        elif balance > -500:
            medium_credits.append(row)
        elif balance > -2000:
            large_credits.append(row)
        else:
            very_large_credits.append(row)
    
    print("\n" + "=" * 80)
    print("CREDIT DISTRIBUTION")
    print("=" * 80)
    print(f"\nSmall (<$50): {len(small_credits):,} (${sum(float(r[5]) for r in small_credits):,.2f})")
    print(f"Medium ($50-$500): {len(medium_credits):,} (${sum(float(r[5]) for r in medium_credits):,.2f})")
    print(f"Large ($500-$2000): {len(large_credits):,} (${sum(float(r[5]) for r in large_credits):,.2f})")
    print(f"Very Large (>$2000): {len(very_large_credits):,} (${sum(float(r[5]) for r in very_large_credits):,.2f})")
    
    # Show very large credits
    print("\n" + "=" * 80)
    print("VERY LARGE CREDITS (>$2000) - PRIORITY FOR REFUND PROCESSING")
    print("=" * 80)
    for row in very_large_credits[:20]:
        charter_id, reserve, date, total, paid, balance, status, cancelled, pay_cnt = row
        print(f"\n{reserve} ({date})")
        print(f"  Total due: ${float(total or 0):,.2f}")
        print(f"  Paid: ${float(paid or 0):,.2f}")
        print(f"  Credit: ${float(balance):,.2f}")
        print(f"  Payments: {pay_cnt}, Status: {status or 'None'}, Cancelled: {cancelled}")
    
    # Check for cancelled charters with credits
    print("\n" + "=" * 80)
    print("CANCELLED CHARTERS WITH CREDITS")
    print("=" * 80)
    cur.execute("""
        SELECT c.reserve_number, c.charter_date, c.balance,
               c.status, c.booking_status
        FROM charters c
        WHERE c.balance < -0.01
        AND (c.cancelled = TRUE 
             OR c.status = 'cancelled' 
             OR c.booking_status = 'cancelled')
        AND NOT EXISTS (
            SELECT 1 FROM charter_refunds cr 
            WHERE cr.charter_id::text = c.reserve_number::text
        )
        ORDER BY c.balance ASC
        LIMIT 20
    """)
    
    cancelled_credits = cur.fetchall()
    if cancelled_credits:
        print(f"\nFound {len(cancelled_credits)} cancelled charters with credits (showing top 20):")
        for reserve, date, balance, status, booking_status in cancelled_credits:
            print(f"  {reserve} ({date}): ${float(balance):,.2f} - {status or booking_status}")
    else:
        print("\nNo cancelled charters with credits found")
    
    # Check charters with high paid_amount but zero or small total_amount_due
    print("\n" + "=" * 80)
    print("SUSPICIOUS PATTERNS - HIGH PAID BUT LOW/ZERO TOTAL")
    print("=" * 80)
    cur.execute("""
        SELECT c.reserve_number, c.charter_date,
               c.total_amount_due, c.paid_amount, c.balance,
               c.status
        FROM charters c
        WHERE c.balance < -0.01
        AND (c.cancelled IS NULL OR c.cancelled = FALSE)
        AND COALESCE(c.total_amount_due, 0) < COALESCE(c.paid_amount, 0) * 0.5
        AND NOT EXISTS (
            SELECT 1 FROM charter_refunds cr 
            WHERE cr.charter_id::text = c.reserve_number::text
        )
        ORDER BY c.balance ASC
        LIMIT 20
    """)
    
    suspicious = cur.fetchall()
    if suspicious:
        print(f"\nFound {len(suspicious)} charters (showing top 20):")
        print("(Likely wrong charter charged or bulk payment misallocation)")
        for reserve, date, total, paid, balance, status in suspicious:
            print(f"  {reserve}: total=${float(total or 0):,.2f}, paid=${float(paid or 0):,.2f}, credit=${float(balance):,.2f}")
    
    # Summary with recommendations
    print("\n" + "=" * 80)
    print("REFUND PROCESSING RECOMMENDATIONS")
    print("=" * 80)
    print(f"\n1. URGENT - Very Large Credits (>$2000): {len(very_large_credits):,} charters (${sum(float(r[5]) for r in very_large_credits):,.2f})")
    print("   Action: Review individually, contact customers, process refunds")
    print(f"\n2. HIGH PRIORITY - Large Credits ($500-$2000): {len(large_credits):,} charters (${sum(float(r[5]) for r in large_credits):,.2f})")
    print("   Action: Batch review, identify customers, confirm refund preference")
    print(f"\n3. MEDIUM - Medium Credits ($50-$500): {len(medium_credits):,} charters (${sum(float(r[5]) for r in medium_credits):,.2f})")
    print("   Action: Consider as customer credit for future bookings")
    print(f"\n4. LOW - Small Credits (<$50): {len(small_credits):,} charters (${sum(float(r[5]) for r in small_credits):,.2f})")
    print("   Action: Write-off or carry as general credit pool")
    
    # Check existing refunds for comparison
    print("\n" + "=" * 80)
    print("EXISTING REFUND RECORDS")
    print("=" * 80)
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount), 0)
        FROM charter_refunds
    """)
    refund_cnt, refund_sum = cur.fetchone()
    print(f"\nTotal refunds in system: {refund_cnt:,} (${float(refund_sum):,.2f})")
    
    # Check how many credits DO have refunds
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(c.balance), 0)
        FROM charters c
        WHERE c.balance < -0.01
        AND (c.cancelled IS NULL OR c.cancelled = FALSE)
        AND EXISTS (
            SELECT 1 FROM charter_refunds cr 
            WHERE cr.charter_id::text = c.reserve_number::text
        )
    """)
    credits_with_refund, credits_with_refund_sum = cur.fetchone()
    
    print(f"Credits WITH refunds documented: {credits_with_refund:,} (${float(credits_with_refund_sum):,.2f})")
    print(f"Credits WITHOUT refunds: {len(credits_no_refund):,} (${float(total_credits_amount):,.2f})")
    
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
