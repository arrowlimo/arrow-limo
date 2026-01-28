#!/usr/bin/env python3
"""Analyze LMS payment structure to understand how payments are recorded."""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor(cursor_factory=RealDictCursor)

# Check unified_map payment structure
print("=== LMS Unified Map Payment Analysis ===\n")
cur.execute("""
    SELECT COUNT(*) as total,
           COUNT(DISTINCT payment_id) as unique_payments,
           COUNT(DISTINCT reserve_no) as unique_reserves
    FROM lms_unified_map
    WHERE payment_id IS NOT NULL
""")
result = cur.fetchone()
print(f"Total payment records: {result['total']}")
print(f"Unique payment IDs: {result['unique_payments']}")
print(f"Unique reserves: {result['unique_reserves']}")

# Multi-charter payments
cur.execute("""
    SELECT payment_id, COUNT(*) as charter_count
    FROM lms_unified_map
    WHERE payment_id IS NOT NULL
    GROUP BY payment_id
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    LIMIT 10
""")
multi = cur.fetchall()
if multi:
    print(f"\nTop multi-charter payments:")
    for m in multi:
        print(f"  Payment {m['payment_id']}: {m['charter_count']} charters")
else:
    print("\nNo multi-charter payments found")

# Check lms_deposits table
print("\n=== LMS Deposits Table ===\n")
cur.execute("""
    SELECT COUNT(*) as total,
           COUNT(DISTINCT deposit_id) as unique_deposits,
           SUM(deposit_amount) as total_deposits
    FROM lms_deposits
""")
result = cur.fetchone()
print(f"Total deposit records: {result['total']}")
print(f"Unique deposits: {result['unique_deposits']}")
print(f"Total deposit amount: ${float(result['total_deposits'] or 0):,.2f}")

# Sample deposits
cur.execute("""
    SELECT deposit_id, deposit_date, deposit_amount, reserve_no
    FROM lms_deposits
    ORDER BY deposit_amount DESC
    LIMIT 5
""")
deposits = cur.fetchall()
print("\nTop 5 deposits:")
for d in deposits:
    print(f"  {d['deposit_id']}: ${float(d['deposit_amount']):,.2f} on {d['deposit_date']} (reserve {d['reserve_no']})")

# Check ALMS payments linked to LMS
print("\n=== ALMS Payments with LMS Data ===\n")
cur.execute("""
    SELECT COUNT(*) as total,
           COUNT(charter_id) as with_charter,
           COUNT(reserve_number) as with_reserve,
           SUM(amount) as total_amount
    FROM payments
    WHERE payment_method = 'credit_card'
      AND payment_key IS NOT NULL
""")
result = cur.fetchone()
print(f"Total Square payments: {result['total']}")
print(f"Linked to charter: {result['with_charter']}")
print(f"With reserve: {result['with_reserve']}")
print(f"Total amount: ${float(result['total_amount'] or 0):,.2f}")

# Check if any LMS deposits match unmatched Square amounts
print("\n=== Checking LMS Deposits vs Unmatched Square ===\n")
cur.execute("""
    WITH unmatched_square AS (
        SELECT payment_id, amount, payment_date
        FROM payments
        WHERE payment_method = 'credit_card'
          AND payment_key IS NOT NULL
          AND charter_id IS NULL
    ),
    potential_matches AS (
        SELECT 
            us.payment_id,
            us.amount as square_amount,
            ld.deposit_id,
            ld.deposit_amount as lms_amount,
            ld.reserve_no,
            ABS(us.amount - ld.deposit_amount) as diff,
            ABS(us.amount - ld.deposit_amount) / NULLIF(us.amount, 0) as pct_diff
        FROM unmatched_square us
        CROSS JOIN lms_deposits ld
        WHERE ABS(us.amount - ld.deposit_amount) / NULLIF(us.amount, 0) <= 0.05
    )
    SELECT COUNT(*) as match_count,
           COUNT(DISTINCT payment_id) as unique_square,
           COUNT(DISTINCT deposit_id) as unique_lms_deposits
    FROM potential_matches
""")
result = cur.fetchone()
print(f"Potential matches (±5%): {result['match_count']}")
print(f"Unique Square payments: {result['unique_square']}")
print(f"Unique LMS deposits: {result['unique_lms_deposits']}")

# Sample potential matches
cur.execute("""
    WITH unmatched_square AS (
        SELECT payment_id, amount, payment_date
        FROM payments
        WHERE payment_method = 'credit_card'
          AND payment_key IS NOT NULL
          AND charter_id IS NULL
    )
    SELECT 
        us.payment_id,
        us.amount as square_amount,
        ld.deposit_id,
        ld.deposit_amount as lms_amount,
        ld.reserve_no,
        ABS(us.amount - ld.deposit_amount) as diff,
        ABS(us.amount - ld.deposit_amount) / NULLIF(us.amount, 0) * 100 as pct_diff
    FROM unmatched_square us
    CROSS JOIN lms_deposits ld
    WHERE ABS(us.amount - ld.deposit_amount) / NULLIF(us.amount, 0) <= 0.05
    ORDER BY us.amount DESC
    LIMIT 10
""")
matches = cur.fetchall()
if matches:
    print("\nTop 10 potential Square ↔ LMS deposit matches:")
    for m in matches:
        print(f"  Square {m['payment_id']} ${float(m['square_amount']):,.2f} → LMS deposit {m['deposit_id']} ${float(m['lms_amount']):,.2f} (reserve {m['reserve_no']}) | diff: {float(m['pct_diff']):.2f}%")

cur.close()
conn.close()
