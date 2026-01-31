#!/usr/bin/env python3
"""
Analyze if unmatched Square payments match LMS deposit totals.
LMS deposits may be split across reserves, so check aggregated amounts.
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import timedelta

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor(cursor_factory=RealDictCursor)

# Get unmatched Square payments
cur.execute("""
    SELECT payment_id, amount, payment_date, payment_key
    FROM payments
    WHERE payment_method = 'credit_card'
      AND payment_key IS NOT NULL
      AND charter_id IS NULL
    ORDER BY amount DESC
""")
square_payments = cur.fetchall()

print(f"=== Unmatched Square Payments Analysis ===\n")
print(f"Total unmatched: {len(square_payments)}")
print(f"Total amount: ${sum(float(p['amount']) for p in square_payments):,.2f}\n")

# Check LMS deposits structure
cur.execute("""
    SELECT COUNT(*) as total,
           COUNT(DISTINCT dep_key) as unique_dep_keys,
           SUM(total) as total_deposits
    FROM lms_deposits
    WHERE total IS NOT NULL
""")
result = cur.fetchone()
print(f"=== LMS Deposits ===")
print(f"Total records: {result['total']}")
print(f"Unique dep_key values: {result['unique_dep_keys']}")
print(f"Total: ${float(result['total_deposits'] or 0):,.2f}\n")

# Check if dep_key groups deposits
cur.execute("""
    SELECT dep_key, COUNT(*) as count, SUM(total) as sum_total
    FROM lms_deposits
    WHERE dep_key IS NOT NULL
    GROUP BY dep_key
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    LIMIT 5
""")
grouped = cur.fetchall()
if grouped:
    print("Sample multi-record dep_keys:")
    for g in grouped:
        print(f"  dep_key {g['dep_key']}: {g['count']} records, total ${float(g['sum_total'] or 0):,.2f}")
    print()

# Now match Square to LMS deposits (individual and aggregated by dep_key)
print(f"=== Matching Square to LMS Deposits ===\n")

# First try exact matches
matched_count = 0
for sq in square_payments[:20]:  # Check top 20 for examples
    sq_amt = round(float(sq['amount']), 2)
    sq_date = sq['payment_date']
    
    # Try exact amount match
    cur.execute("""
        SELECT id, dep_key, dep_date, total, number
        FROM lms_deposits
        WHERE ABS(total - %s) < 0.01
          AND dep_date BETWEEN %s AND %s
        LIMIT 5
    """, (sq_amt, sq_date - timedelta(days=7), sq_date + timedelta(days=7)))
    
    exact_matches = cur.fetchall()
    if exact_matches:
        print(f"Square {sq['payment_id']} ${sq_amt:,.2f} on {sq_date}:")
        for em in exact_matches:
            print(f"  → LMS deposit {em['id']} (dep_key {em['dep_key']}): ${float(em['total']):,.2f} on {em['dep_date']} (number {em['number']})")
        matched_count += 1
        print()

if matched_count == 0:
    print("No exact matches found. Trying aggregated dep_key totals...\n")
    
    # Try aggregated by dep_key
    for sq in square_payments[:20]:
        sq_amt = round(float(sq['amount']), 2)
        sq_date = sq['payment_date']
        
        # Find dep_keys where total matches
        cur.execute("""
            SELECT dep_key, SUM(total) as sum_total, COUNT(*) as count,
                   STRING_AGG(number::text, ', ' ORDER BY id) as numbers
            FROM lms_deposits
            WHERE dep_date BETWEEN %s AND %s
              AND dep_key IS NOT NULL
            GROUP BY dep_key
            HAVING ABS(SUM(total) - %s) < 0.01
            LIMIT 3
        """, (sq_date - timedelta(days=7), sq_date + timedelta(days=7), sq_amt))
        
        agg_matches = cur.fetchall()
        if agg_matches:
            print(f"Square {sq['payment_id']} ${sq_amt:,.2f} on {sq_date}:")
            for am in agg_matches:
                print(f"  → LMS dep_key {am['dep_key']}: ${float(am['sum_total']):,.2f} across {am['count']} deposits (numbers: {am['numbers']})")
            matched_count += 1
            print()

print(f"\nFound matches for {matched_count} of top 20 Square payments")

# Get overall stats on potential matches
cur.execute("""
    WITH unmatched_square AS (
        SELECT payment_id, amount, payment_date
        FROM payments
        WHERE payment_method = 'credit_card'
          AND payment_key IS NOT NULL
          AND charter_id IS NULL
    ),
    exact_matches AS (
        SELECT us.payment_id, ld.id as deposit_id
        FROM unmatched_square us
        JOIN lms_deposits ld ON ABS(ld.total - us.amount) < 0.01
                            AND ld.dep_date BETWEEN us.payment_date - INTERVAL '7 days'
                                                AND us.payment_date + INTERVAL '7 days'
    )
    SELECT COUNT(DISTINCT payment_id) as matched_square,
           COUNT(DISTINCT deposit_id) as matched_deposits
    FROM exact_matches
""")
result = cur.fetchone()
print(f"\n=== Overall Exact Match Stats (±7 days, exact amount) ===")
print(f"Square payments with matches: {result['matched_square']}")
print(f"LMS deposits involved: {result['matched_deposits']}")

cur.close()
conn.close()
