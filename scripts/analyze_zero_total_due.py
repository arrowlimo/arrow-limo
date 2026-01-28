#!/usr/bin/env python
"""
Analyze charters with $0 total_amount_due to understand how to populate them.
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
    print("CHARTERS WITH $0 TOTAL_AMOUNT_DUE ANALYSIS")
    print("=" * 80)
    
    # Count charters with $0 total_due
    cur.execute("""
        SELECT COUNT(*),
               COALESCE(SUM(paid_amount), 0) AS paid_sum,
               COALESCE(SUM(balance), 0) AS balance_sum
        FROM charters
        WHERE COALESCE(total_amount_due, 0) = 0
        AND COALESCE(paid_amount, 0) > 0
    """)
    count, paid_sum, balance_sum = cur.fetchone()
    
    print(f"\nCharters with $0 total_due but payments received: {count:,}")
    print(f"Total paid into these charters: ${float(paid_sum):,.2f}")
    print(f"Total balance (all negative): ${float(balance_sum):,.2f}")
    
    # Check if rate field is populated
    print("\n" + "=" * 80)
    print("RATE FIELD ANALYSIS")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) FILTER(WHERE rate > 0) AS with_rate,
            COUNT(*) FILTER(WHERE rate IS NULL OR rate = 0) AS without_rate,
            COALESCE(SUM(rate) FILTER(WHERE rate > 0), 0) AS rate_sum,
            COALESCE(SUM(paid_amount) FILTER(WHERE rate > 0), 0) AS paid_with_rate,
            COALESCE(SUM(paid_amount) FILTER(WHERE rate IS NULL OR rate = 0), 0) AS paid_without_rate
        FROM charters
        WHERE COALESCE(total_amount_due, 0) = 0
        AND COALESCE(paid_amount, 0) > 0
    """)
    with_rate, without_rate, rate_sum, paid_with, paid_without = cur.fetchone()
    
    print(f"\nWith rate > 0: {with_rate:,} (rate sum: ${float(rate_sum):,.2f}, paid: ${float(paid_with):,.2f})")
    print(f"Without rate: {without_rate:,} (paid: ${float(paid_without):,.2f})")
    
    # Sample records with rate
    print("\nSample charters with rate (first 10):")
    cur.execute("""
        SELECT reserve_number, charter_date, rate, paid_amount, balance, status
        FROM charters
        WHERE COALESCE(total_amount_due, 0) = 0
        AND COALESCE(paid_amount, 0) > 0
        AND rate > 0
        ORDER BY paid_amount DESC
        LIMIT 10
    """)
    for row in cur.fetchall():
        reserve, date, rate, paid, balance, status = row
        print(f"  {reserve}: rate=${float(rate):,.2f}, paid=${float(paid):,.2f}, bal=${float(balance):,.2f}, {status}")
    
    # Compare rate vs paid_amount
    print("\n" + "=" * 80)
    print("RATE VS PAID COMPARISON")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) FILTER(WHERE ABS(rate - paid_amount) < 0.02) AS matches,
            COUNT(*) FILTER(WHERE paid_amount > rate * 0.9 AND paid_amount < rate * 1.1) AS close_match,
            COUNT(*) FILTER(WHERE paid_amount < rate * 0.9 OR paid_amount > rate * 1.1) AS mismatch
        FROM charters
        WHERE COALESCE(total_amount_due, 0) = 0
        AND COALESCE(paid_amount, 0) > 0
        AND rate > 0
    """)
    matches, close, mismatch = cur.fetchone()
    
    print(f"\nRate = paid_amount (within $0.02): {matches:,}")
    print(f"Rate ≈ paid_amount (within 10%): {close:,}")
    print(f"Rate ≠ paid_amount (>10% diff): {mismatch:,}")
    
    # Check charter_charges table
    print("\n" + "=" * 80)
    print("CHARTER_CHARGES TABLE LOOKUP")
    print("=" * 80)
    
    cur.execute("""
        SELECT COUNT(DISTINCT c.reserve_number)
        FROM charters c
        WHERE COALESCE(c.total_amount_due, 0) = 0
        AND COALESCE(c.paid_amount, 0) > 0
        AND EXISTS (
            SELECT 1 FROM charter_charges cc 
            WHERE cc.charter_id = c.charter_id
        )
    """)
    with_charges = cur.fetchone()[0]
    
    print(f"\nCharters with entries in charter_charges: {with_charges:,} of {count:,}")
    
    # Sample charter_charges sums
    if with_charges > 0:
        print("\nSample charter_charges totals (first 10):")
        cur.execute("""
            SELECT c.reserve_number, 
                   COALESCE(SUM(cc.amount), 0) AS charges_sum,
                   c.paid_amount,
                   c.rate
            FROM charters c
            JOIN charter_charges cc ON cc.charter_id = c.charter_id
            WHERE COALESCE(c.total_amount_due, 0) = 0
            AND COALESCE(c.paid_amount, 0) > 0
            GROUP BY c.reserve_number, c.paid_amount, c.rate
            ORDER BY charges_sum DESC
            LIMIT 10
        """)
        for row in cur.fetchall():
            reserve, charges, paid, rate = row
            print(f"  {reserve}: charges=${float(charges):,.2f}, paid=${float(paid):,.2f}, rate=${float(rate) if rate else 0:.2f}")
    
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
