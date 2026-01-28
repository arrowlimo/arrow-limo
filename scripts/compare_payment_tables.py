#!/usr/bin/env python3
"""
Analyze charter_payments vs payments tables for potential consolidation.
Check for duplicates, unique records, and schema differences.
"""

import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

print("="*80)
print("CHARTER_PAYMENTS vs PAYMENTS ANALYSIS")
print("="*80)

# 1. Row counts
cur.execute("SELECT COUNT(*) FROM payments")
payments_count = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM charter_payments")
charter_payments_count = cur.fetchone()[0]

print(f"\nRow counts:")
print(f"  payments: {payments_count:,}")
print(f"  charter_payments: {charter_payments_count:,}")

# 2. Schema comparison
print("\n" + "="*80)
print("SCHEMA COMPARISON")
print("="*80)

cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'payments'
    ORDER BY ordinal_position
""")
payments_cols = {col[0]: (col[1], col[2]) for col in cur.fetchall()}

cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'charter_payments'
    ORDER BY ordinal_position
""")
charter_payments_cols = {col[0]: (col[1], col[2]) for col in cur.fetchall()}

print("\nColumns in PAYMENTS only:")
for col in sorted(set(payments_cols.keys()) - set(charter_payments_cols.keys())):
    print(f"  {col:<30} {payments_cols[col][0]}")

print("\nColumns in CHARTER_PAYMENTS only:")
for col in sorted(set(charter_payments_cols.keys()) - set(payments_cols.keys())):
    print(f"  {col:<30} {charter_payments_cols[col][0]}")

print("\nCommon columns:")
common_cols = sorted(set(payments_cols.keys()) & set(charter_payments_cols.keys()))
for col in common_cols:
    print(f"  {col:<30} {payments_cols[col][0]}")

# 3. Check for overlapping records
print("\n" + "="*80)
print("OVERLAP ANALYSIS")
print("="*80)

# Check if charter_payments records exist in payments by payment_key
cur.execute("""
    SELECT COUNT(*) 
    FROM charter_payments cp
    INNER JOIN payments p 
        ON cp.payment_key = p.payment_key
""")
overlap_by_key = cur.fetchone()[0]

print(f"\nRecords matching by payment_key:")
print(f"  {overlap_by_key:,} / {charter_payments_count:,} ({overlap_by_key/charter_payments_count*100:.1f}%)")

# Also check by amount+date match
cur.execute("""
    SELECT COUNT(*) 
    FROM charter_payments cp
    WHERE EXISTS (
        SELECT 1 FROM payments p 
        WHERE cp.amount = p.amount
        AND cp.payment_date = p.payment_date
        AND COALESCE(cp.payment_method, 'unknown') = COALESCE(p.payment_method, 'unknown')
    )
""")
overlap_by_fields = cur.fetchone()[0]

print(f"\nRecords matching by amount+date+method:")
print(f"  {overlap_by_fields:,} / {charter_payments_count:,} ({overlap_by_fields/charter_payments_count*100:.1f}%)")

# Records unique to charter_payments (by payment_key)
cur.execute("""
    SELECT COUNT(*) 
    FROM charter_payments cp
    WHERE cp.payment_key NOT IN (SELECT payment_key FROM payments WHERE payment_key IS NOT NULL)
""")
unique_charter_payments = cur.fetchone()[0]

print(f"\nRecords UNIQUE to charter_payments (by payment_key):")
print(f"  {unique_charter_payments:,}")

# 4. Sample unique charter_payments records
if unique_charter_payments > 0:
    print("\n" + "="*80)
    print("SAMPLE UNIQUE CHARTER_PAYMENTS (first 10)")
    print("="*80)
    
    cur.execute("""
        SELECT cp.charter_id, cp.payment_date, cp.amount, cp.payment_method, cp.payment_key
        FROM charter_payments cp
        WHERE cp.payment_key NOT IN (SELECT payment_key FROM payments WHERE payment_key IS NOT NULL)
        ORDER BY cp.payment_date DESC
        LIMIT 10
    """)
    
    print(f"\n{'Charter':<12} {'Date':<12} {'Amount':<12} {'Method':<20} {'Key':<20}")
    print("-"*80)
    for row in cur.fetchall():
        charter_id = row[0] or 'N/A'
        date = str(row[1]) if row[1] else 'N/A'
        amount = f"${row[2]:,.2f}" if row[2] else 'N/A'
        method = row[3] or 'unknown'
        key = row[4] or 'N/A'
        print(f"{charter_id:<12} {date:<12} {amount:<12} {method:<20} {key:<20}")

# 5. Check for records in payments but not charter_payments
cur.execute("""
    SELECT COUNT(*) 
    FROM payments p
    WHERE p.payment_key NOT IN (SELECT payment_key FROM charter_payments WHERE payment_key IS NOT NULL)
""")
unique_payments = cur.fetchone()[0]

print("\n" + "="*80)
print(f"\nRecords UNIQUE to payments (not in charter_payments):")
print(f"  {unique_payments:,}")

# 6. Recommendation
print("\n" + "="*80)
print("RECOMMENDATION")
print("="*80)

if unique_charter_payments == 0:
    print("\n✅ charter_payments is a SUBSET of payments")
    print("   Safe to drop charter_payments table")
elif unique_charter_payments < 100:
    print(f"\n⚠️  charter_payments has {unique_charter_payments} unique records")
    print("   Review unique records before consolidation")
else:
    print(f"\n❌ charter_payments has {unique_charter_payments:,} unique records")
    print("   Migrate unique records to payments before dropping")

if unique_payments > 0:
    print(f"\n✅ payments has {unique_payments:,} records not in charter_payments")
    print("   payments is the PRIMARY table (more complete)")

cur.close()
conn.close()
