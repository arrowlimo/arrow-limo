#!/usr/bin/env python3
"""
Check for exact duplicates between gl_transactions_staging and unified_general_ledger.
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

conn = get_db_connection()
cur = conn.cursor()

print("=" * 80)
print("DUPLICATE DETECTION: gl_transactions_staging vs unified_general_ledger")
print("=" * 80)

# Check for matches by date, account, and amounts
print("\n1. EXACT MATCHES (date + account + debit + credit)")
print("-" * 80)

cur.execute("""
    SELECT COUNT(*) as match_count
    FROM gl_transactions_staging gts
    JOIN unified_general_ledger ugl ON (
        gts.transaction_date = ugl.transaction_date
        AND gts.account_name = ugl.account_code
        AND COALESCE(gts.debit_amount, 0) = COALESCE(ugl.debit_amount, 0)
        AND COALESCE(gts.credit_amount, 0) = COALESCE(ugl.credit_amount, 0)
    )
""")

match_count = cur.fetchone()[0]
staging_total = 50947

print(f"Staging rows with exact matches in UGL: {match_count:,}")
print(f"Staging total rows: {staging_total:,}")
print(f"Match rate: {match_count/staging_total*100:.1f}%")
print(f"Unmatched staging rows: {staging_total - match_count:,}")

# Check unmatched rows
print("\n2. UNMATCHED STAGING ROWS ANALYSIS")
print("-" * 80)

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM gts.transaction_date) as year,
        COUNT(*) as unmatched_count,
        SUM(COALESCE(gts.debit_amount, 0)) as total_debits,
        SUM(COALESCE(gts.credit_amount, 0)) as total_credits
    FROM gl_transactions_staging gts
    LEFT JOIN unified_general_ledger ugl ON (
        gts.transaction_date = ugl.transaction_date
        AND gts.account_name = ugl.account_code
        AND COALESCE(gts.debit_amount, 0) = COALESCE(ugl.debit_amount, 0)
        AND COALESCE(gts.credit_amount, 0) = COALESCE(ugl.credit_amount, 0)
    )
    WHERE ugl.id IS NULL
    GROUP BY EXTRACT(YEAR FROM gts.transaction_date)
    ORDER BY year
""")

print(f"{'Year':<6} {'Unmatched':>10} {'Debits':>18} {'Credits':>18}")
print("-" * 60)
total_unmatched = 0
for year, count, debits, credits in cur.fetchall():
    total_unmatched += count
    print(f"{int(year):<6} {count:>10,} ${debits:>15,.2f} ${credits:>15,.2f}")

print(f"\nTotal unmatched: {total_unmatched:,}")

# Sample unmatched rows
print("\n3. SAMPLE UNMATCHED ROWS (First 10)")
print("-" * 80)

cur.execute("""
    SELECT 
        gts.transaction_date,
        gts.account_name,
        gts.debit_amount,
        gts.credit_amount,
        gts.description
    FROM gl_transactions_staging gts
    LEFT JOIN unified_general_ledger ugl ON (
        gts.transaction_date = ugl.transaction_date
        AND gts.account_name = ugl.account_code
        AND COALESCE(gts.debit_amount, 0) = COALESCE(ugl.debit_amount, 0)
        AND COALESCE(gts.credit_amount, 0) = COALESCE(ugl.credit_amount, 0)
    )
    WHERE ugl.id IS NULL
    ORDER BY gts.transaction_date
    LIMIT 10
""")

for row in cur.fetchall():
    txn_date, account, debit, credit, desc = row
    print(f"{txn_date} | {account[:40]:40} | Dr: ${debit or 0:>10,.2f} Cr: ${credit or 0:>10,.2f}")
    if desc:
        print(f"  {desc[:70]}")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("RECOMMENDATION:")
print("=" * 80)

if match_count / staging_total > 0.95:
    print("""
HIGH DUPLICATE RATE (>95%) - ARCHIVE STAGING TABLE

The gl_transactions_staging table contains mostly duplicate data already in
unified_general_ledger. Recommend:

1. Archive the staging table (rename to gl_transactions_staging_ARCHIVED_20251107)
2. Investigate the small number of unmatched rows
3. If unmatched rows are legitimate new data, promote selectively
4. Otherwise, drop the staging table as it serves no purpose
""")
elif match_count / staging_total > 0.70:
    print("""
MODERATE DUPLICATE RATE (70-95%) - SELECTIVE PROMOTION

The staging table contains significant duplicates but also some new data.
Recommend:

1. Create selective promotion script for unmatched rows only
2. Validate unmatched rows before promotion
3. Mark staging table as processed after promotion
""")
else:
    print("""
LOW DUPLICATE RATE (<70%) - FULL PROMOTION

The staging table contains mostly new data. Recommend:

1. Review data quality of staging table
2. Create full promotion script to unified_general_ledger
3. Handle any existing duplicates with upsert logic
""")
