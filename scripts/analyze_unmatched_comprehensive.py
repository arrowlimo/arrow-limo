#!/usr/bin/env python
"""
Comprehensive analysis of unmatched payments - updated for post-fix analysis.
"""
import psycopg2
from collections import defaultdict


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
    print("COMPREHENSIVE UNMATCHED PAYMENT ANALYSIS (POST-FIX)")
    print("=" * 80)
    
    # Overall stats
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(COALESCE(p.payment_amount, p.amount)), 0)
        FROM payments p
        WHERE NOT EXISTS (
            SELECT 1 FROM charter_payments cp WHERE cp.payment_id = p.payment_id
        )
    """)
    total_unmatched, total_amount = cur.fetchone()
    print(f"\nTotal unmatched: {total_unmatched:,} payments (${float(total_amount):,.2f})")
    
    # By payment key pattern (source indicator)
    print("\n" + "=" * 80)
    print("BREAKDOWN BY PAYMENT_KEY PATTERN")
    print("=" * 80)
    cur.execute("""
        SELECT 
            CASE 
                WHEN payment_key LIKE 'BTX:%' THEN 'Banking/Interac'
                WHEN payment_key LIKE 'LMSDEP:%' THEN 'LMS Deposit'
                WHEN payment_key LIKE 'QBO:%' THEN 'QuickBooks Online'
                WHEN payment_key LIKE 'SQ:%' THEN 'Square'
                WHEN payment_key ~ '^[0-9]+$' THEN 'Numeric Key'
                WHEN payment_key IS NULL THEN 'NULL Key'
                ELSE 'Other Pattern'
            END AS key_pattern,
            COUNT(*) AS cnt,
            COALESCE(SUM(COALESCE(p.payment_amount, p.amount)), 0) AS amt
        FROM payments p
        WHERE NOT EXISTS (
            SELECT 1 FROM charter_payments cp WHERE cp.payment_id = p.payment_id
        )
        GROUP BY key_pattern
        ORDER BY cnt DESC
    """)
    for pattern, cnt, amt in cur.fetchall():
        print(f"  {pattern}: {cnt:,} (${float(amt):,.2f})")
    
    # By payment method
    print("\n" + "=" * 80)
    print("BREAKDOWN BY PAYMENT METHOD")
    print("=" * 80)
    cur.execute("""
        SELECT COALESCE(p.payment_method, 'None') AS method,
               COUNT(*) AS cnt,
               COALESCE(SUM(COALESCE(p.payment_amount, p.amount)), 0) AS amt
        FROM payments p
        WHERE NOT EXISTS (
            SELECT 1 FROM charter_payments cp WHERE cp.payment_id = p.payment_id
        )
        GROUP BY method
        ORDER BY cnt DESC
        LIMIT 15
    """)
    for method, cnt, amt in cur.fetchall():
        print(f"  {method}: {cnt:,} (${float(amt):,.2f})")
    
    # Check bulk deposits
    print("\n" + "=" * 80)
    print("BULK DEPOSITS (>$10,000)")
    print("=" * 80)
    cur.execute("""
        SELECT p.payment_id, 
               COALESCE(p.payment_amount, p.amount) AS amt,
               p.payment_date, p.account_number, p.payment_method,
               p.payment_key, p.notes
        FROM payments p
        WHERE NOT EXISTS (
            SELECT 1 FROM charter_payments cp WHERE cp.payment_id = p.payment_id
        )
        AND COALESCE(p.payment_amount, p.amount) > 10000
        ORDER BY amt DESC
        LIMIT 20
    """)
    bulk = cur.fetchall()
    print(f"\nFound {len(bulk)} bulk deposits:")
    for pid, amt, date, acct, method, key, notes in bulk:
        print(f"\n  PID {pid}: ${float(amt):,.2f} on {date}")
        print(f"    Account: {acct or 'None'}, Method: {method or 'None'}")
        print(f"    Key: {key or 'None'}")
        if notes:
            print(f"    Notes: {notes[:80]}")
    
    # Check matchable by account_number
    print("\n" + "=" * 80)
    print("MATCHABLE BY ACCOUNT_NUMBER (±90 days, >$0)")
    print("=" * 80)
    cur.execute("""
        WITH unmatched AS (
            SELECT p.payment_id, p.account_number, p.payment_date,
                   COALESCE(p.payment_amount, p.amount) AS amt
            FROM payments p
            WHERE NOT EXISTS (
                SELECT 1 FROM charter_payments cp WHERE cp.payment_id = p.payment_id
            )
            AND p.account_number IS NOT NULL
            AND COALESCE(p.payment_amount, p.amount) > 0
        )
        SELECT COUNT(DISTINCT u.payment_id)
        FROM unmatched u
        WHERE EXISTS (
            SELECT 1 FROM charters c
            WHERE c.account_number = u.account_number
            AND c.charter_date BETWEEN u.payment_date::date - INTERVAL '90 days'
                                   AND u.payment_date::date + INTERVAL '90 days'
            AND c.balance > 0.01
        )
    """)
    matchable_acct = cur.fetchone()[0]
    print(f"\nPotentially matchable by account: {matchable_acct:,}")
    
    # Sample matchable
    if matchable_acct > 0:
        print("\nSample matchable (first 10):")
        cur.execute("""
            WITH unmatched AS (
                SELECT p.payment_id, p.account_number, p.payment_date,
                       COALESCE(p.payment_amount, p.amount) AS amt
                FROM payments p
                WHERE NOT EXISTS (
                    SELECT 1 FROM charter_payments cp WHERE cp.payment_id = p.payment_id
                )
                AND p.account_number IS NOT NULL
                AND COALESCE(p.payment_amount, p.amount) > 0
            ),
            matches AS (
                SELECT u.payment_id, u.amt, u.payment_date,
                       c.reserve_number, c.charter_date, c.balance,
                       ABS(EXTRACT(EPOCH FROM (c.charter_date::timestamp - u.payment_date::timestamp))) AS days_diff
                FROM unmatched u
                JOIN charters c ON c.account_number = u.account_number
                WHERE c.charter_date BETWEEN u.payment_date::date - INTERVAL '90 days'
                                         AND u.payment_date::date + INTERVAL '90 days'
                AND c.balance > 0.01
            )
            SELECT payment_id, amt, payment_date, reserve_number, charter_date, balance, days_diff / 86400 AS days
            FROM matches
            ORDER BY amt DESC
            LIMIT 10
        """)
        for pid, amt, pdate, reserve, cdate, bal, days in cur.fetchall():
            print(f"  PID {pid}: ${float(amt):,.2f} ({pdate}) → {reserve} ({cdate}, owes ${float(bal):,.2f}) [{int(days)} days]")
    
    # Check zero/negative amounts
    print("\n" + "=" * 80)
    print("ZERO OR NEGATIVE AMOUNTS")
    print("=" * 80)
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(COALESCE(p.payment_amount, p.amount)), 0)
        FROM payments p
        WHERE NOT EXISTS (
            SELECT 1 FROM charter_payments cp WHERE cp.payment_id = p.payment_id
        )
        AND COALESCE(p.payment_amount, p.amount) <= 0
    """)
    zero_cnt, zero_sum = cur.fetchone()
    print(f"\nZero/negative payments: {zero_cnt:,} (${float(zero_sum):,.2f})")
    
    # Check payments with reserve_number but no matching charter
    print("\n" + "=" * 80)
    print("PAYMENTS WITH RESERVE_NUMBER BUT NO CHARTER EXISTS")
    print("=" * 80)
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(COALESCE(p.payment_amount, p.amount)), 0)
        FROM payments p
        WHERE NOT EXISTS (
            SELECT 1 FROM charter_payments cp WHERE cp.payment_id = p.payment_id
        )
        AND p.reserve_number IS NOT NULL
        AND p.reserve_number <> ''
        AND NOT EXISTS (
            SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
        )
    """)
    orphan_cnt, orphan_sum = cur.fetchone()
    print(f"\nOrphan payments (reserve points to non-existent charter): {orphan_cnt:,} (${float(orphan_sum):,.2f})")
    
    if orphan_cnt > 0 and orphan_cnt <= 20:
        print("\nAll orphan payments:")
        cur.execute("""
            SELECT p.payment_id, p.reserve_number, 
                   COALESCE(p.payment_amount, p.amount) AS amt,
                   p.payment_date
            FROM payments p
            WHERE NOT EXISTS (
                SELECT 1 FROM charter_payments cp WHERE cp.payment_id = p.payment_id
            )
            AND p.reserve_number IS NOT NULL
            AND p.reserve_number <> ''
            AND NOT EXISTS (
                SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
            )
            ORDER BY amt DESC
        """)
        for pid, reserve, amt, date in cur.fetchall():
            print(f"  PID {pid}: Reserve {reserve}, ${float(amt):,.2f}, {date}")
    
    # Summary
    print("\n" + "=" * 80)
    print("MATCHING OPPORTUNITIES SUMMARY")
    print("=" * 80)
    print(f"\nTotal unmatched: {total_unmatched:,}")
    print(f"  Matchable by account_number: {matchable_acct:,}")
    print(f"  Zero/negative amounts: {zero_cnt:,}")
    print(f"  Orphan reserve_numbers: {orphan_cnt:,}")
    print(f"  Bulk deposits (>$10K): {len(bulk):,}")
    remaining = total_unmatched - matchable_acct - zero_cnt - orphan_cnt
    print(f"  Remaining for investigation: ~{remaining:,}")
    
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
