#!/usr/bin/env python3
"""
Detailed analysis of charter_payments duplicates and migration status.
"""

import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

print("="*80)
print("CHARTER_PAYMENTS MIGRATION STATUS")
print("="*80)

# 1. NULL payment_key analysis
cur.execute("SELECT COUNT(*) FROM charter_payments WHERE payment_key IS NULL")
null_keys = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM charter_payments WHERE payment_key IS NOT NULL")
has_keys = cur.fetchone()[0]

print(f"\nPayment key status:")
print(f"  NULL payment_key:     {null_keys:>6,} ({null_keys/25413*100:.1f}%)")
print(f"  Has payment_key:      {has_keys:>6,} ({has_keys/25413*100:.1f}%)")

# 2. Check for duplicates within charter_payments
cur.execute("""
    SELECT payment_key, COUNT(*) as count
    FROM charter_payments
    WHERE payment_key IS NOT NULL
    GROUP BY payment_key
    HAVING COUNT(*) > 1
    ORDER BY count DESC
    LIMIT 10
""")

duplicates = cur.fetchall()
if duplicates:
    print(f"\n⚠️  DUPLICATES in charter_payments (top 10 payment_keys):")
    print(f"\n{'Payment Key':<20} {'Count':<10}")
    print("-"*80)
    for key, count in duplicates:
        print(f"{key or 'None':<20} {count:<10}")
    
    cur.execute("""
        SELECT COUNT(DISTINCT payment_key)
        FROM charter_payments
        WHERE payment_key IS NOT NULL
        GROUP BY payment_key
        HAVING COUNT(*) > 1
    """)
    result = cur.fetchone()
    total_dupe_keys = result[0] if result else 0
    print(f"\nDistinct payment_keys with duplicates: {total_dupe_keys}")

# 3. Check if NULL key records are already in payments by amount+date
cur.execute("""
    SELECT COUNT(*)
    FROM charter_payments cp
    WHERE cp.payment_key IS NULL
    AND EXISTS (
        SELECT 1 FROM payments p
        WHERE cp.amount = p.amount
        AND cp.payment_date = p.payment_date
        AND COALESCE(cp.payment_method, 'unknown') = COALESCE(p.payment_method, 'unknown')
    )
""")
null_but_matched = cur.fetchone()[0]

print(f"\n" + "="*80)
print("NULL payment_key records that MATCH payments (by amount/date/method):")
print(f"  {null_but_matched:,} / {null_keys:,} ({null_but_matched/null_keys*100:.1f}%)")

cur.execute("""
    SELECT COUNT(*)
    FROM charter_payments cp
    WHERE cp.payment_key IS NULL
    AND NOT EXISTS (
        SELECT 1 FROM payments p
        WHERE cp.amount = p.amount
        AND cp.payment_date = p.payment_date
        AND COALESCE(cp.payment_method, 'unknown') = COALESCE(p.payment_method, 'unknown')
    )
""")
null_no_match = cur.fetchone()[0]

print(f"\nNULL payment_key records with NO match in payments:")
print(f"  {null_no_match:,}")

# 4. Sample unmatchable NULL key records
if null_no_match > 0:
    print(f"\nSample unmatchable records (first 20):")
    print("-"*80)
    cur.execute("""
        SELECT cp.charter_id, cp.payment_date, cp.amount, cp.payment_method, cp.client_name
        FROM charter_payments cp
        WHERE cp.payment_key IS NULL
        AND NOT EXISTS (
            SELECT 1 FROM payments p
            WHERE cp.amount = p.amount
            AND cp.payment_date = p.payment_date
            AND COALESCE(cp.payment_method, 'unknown') = COALESCE(p.payment_method, 'unknown')
        )
        ORDER BY cp.payment_date DESC
        LIMIT 20
    """)
    
    print(f"\n{'Charter':<10} {'Date':<12} {'Amount':<12} {'Method':<15} {'Client':<30}")
    print("-"*80)
    for row in cur.fetchall():
        charter = row[0] or 'N/A'
        date = str(row[1]) if row[1] else 'N/A'
        amount = f"${row[2]:,.2f}" if row[2] else 'N/A'
        method = row[3] or 'unknown'
        client = (row[4] or 'N/A')[:30]
        print(f"{charter:<10} {date:<12} {amount:<12} {method:<15} {client:<30}")

# 5. Check date range of unmatchable
if null_no_match > 0:
    cur.execute("""
        SELECT MIN(payment_date), MAX(payment_date)
        FROM charter_payments cp
        WHERE cp.payment_key IS NULL
        AND NOT EXISTS (
            SELECT 1 FROM payments p
            WHERE cp.amount = p.amount
            AND cp.payment_date = p.payment_date
            AND COALESCE(cp.payment_method, 'unknown') = COALESCE(p.payment_method, 'unknown')
        )
    """)
    min_date, max_date = cur.fetchone()
    print(f"\nDate range of unmatchable: {min_date} to {max_date}")

print("\n" + "="*80)
print("RECOMMENDATION")
print("="*80)

if null_no_match == 0:
    print("\n✅ All charter_payments records are either:")
    print("   - Already in payments (by payment_key), OR")
    print("   - Matchable by amount/date/method")
    print("\n   SAFE TO DROP charter_payments table")
elif null_no_match < 50:
    print(f"\n⚠️  {null_no_match} records need review")
    print("   Manual verification recommended before dropping table")
else:
    print(f"\n❌ {null_no_match:,} unmatchable records")
    print("   Investigate why these payments are not in main payments table")
    print("   Consider migrating before dropping charter_payments")

cur.close()
conn.close()
