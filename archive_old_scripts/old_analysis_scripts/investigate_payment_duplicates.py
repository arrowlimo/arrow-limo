#!/usr/bin/env python3
"""
Investigate payment duplicates found in Neon database.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os
import json
from datetime import datetime

load_dotenv()

neon_conn = psycopg2.connect(os.getenv("NEON_DATABASE_URL"))

print("=" * 80)
print("PAYMENT DUPLICATE INVESTIGATION")
print("=" * 80)
print()

# First, check the 11 duplicates for charter 017720
print("=" * 80)
print("CHARTER 017720 - 11 DUPLICATE PAYMENTS")
print("=" * 80)
print()

with neon_conn.cursor(cursor_factory=RealDictCursor) as cur:
    cur.execute("""
        SELECT *
        FROM payments
        WHERE reserve_number = '017720'
        AND payment_date = '2023-07-04'
        AND amount = 102.00
        ORDER BY payment_id
    """)
    
    duplicates = cur.fetchall()
    print(f"Found {len(duplicates)} records:")
    print()
    
    for i, rec in enumerate(duplicates, 1):
        print(f"Record {i}:")
        print(f"  payment_id: {rec['payment_id']}")
        print(f"  reserve_number: {rec['reserve_number']}")
        print(f"  payment_date: {rec['payment_date']}")
        print(f"  amount: ${rec['amount']:.2f}")
        print(f"  payment_method: {rec.get('payment_method', 'N/A')}")
        print(f"  reference_number: {rec.get('reference_number', 'N/A')}")
        print(f"  notes: {rec.get('notes', 'N/A')[:50]}")
        print(f"  created_at: {rec.get('created_at', 'N/A')}")
        print()

# Check all duplicate patterns
print("=" * 80)
print("ALL DUPLICATE PAYMENT PATTERNS")
print("=" * 80)
print()

with neon_conn.cursor(cursor_factory=RealDictCursor) as cur:
    cur.execute("""
        WITH duplicates AS (
            SELECT 
                reserve_number,
                payment_date,
                amount,
                COUNT(*) as count,
                ARRAY_AGG(payment_id ORDER BY payment_id) as payment_ids,
                MIN(payment_id) as first_id,
                MAX(payment_id) as last_id
            FROM payments
            WHERE reserve_number IS NOT NULL 
            AND payment_date IS NOT NULL
            AND amount IS NOT NULL
            GROUP BY reserve_number, payment_date, amount
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC, reserve_number
        )
        SELECT * FROM duplicates
    """)
    
    all_dups = cur.fetchall()
    
    print(f"Found {len(all_dups)} duplicate payment patterns:")
    print()
    print(f"{'Reserve':<10} {'Date':<12} {'Amount':>12} {'Count':>6} {'Payment IDs'}")
    print("-" * 80)
    
    total_duplicate_payments = 0
    for dup in all_dups:
        ids_str = str(dup['payment_ids'])[:40]
        print(f"{dup['reserve_number']:<10} {str(dup['payment_date']):<12} ${dup['amount']:>10,.2f} {dup['count']:>6} {ids_str}")
        total_duplicate_payments += dup['count']
    
    print()
    print(f"Total duplicate payments: {total_duplicate_payments:,}")
    print(f"Excess duplicates (to delete): {total_duplicate_payments - len(all_dups):,}")

# Analyze NULL values
print()
print("=" * 80)
print("NULL VALUE ANALYSIS")
print("=" * 80)
print()

with neon_conn.cursor(cursor_factory=RealDictCursor) as cur:
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE reserve_number IS NULL) as null_reserve,
            COUNT(*) FILTER (WHERE payment_date IS NULL) as null_date,
            COUNT(*) FILTER (WHERE amount IS NULL) as null_amount,
            COUNT(*) FILTER (WHERE payment_method IS NULL) as null_method,
            COUNT(*) as total
        FROM payments
    """)
    
    nulls = cur.fetchone()
    print(f"NULL value counts:")
    print(f"  reserve_number: {nulls['null_reserve']:>6,}")
    print(f"  payment_date:   {nulls['null_date']:>6,}")
    print(f"  amount:         {nulls['null_amount']:>6,}")
    print(f"  payment_method: {nulls['null_method']:>6,}")
    print(f"  Total rows:     {nulls['total']:>6,}")

# Create deletion script
print()
print("=" * 80)
print("GENERATING DELETION SCRIPT")
print("=" * 80)
print()

with neon_conn.cursor(cursor_factory=RealDictCursor) as cur:
    cur.execute("""
        WITH duplicates AS (
            SELECT 
                reserve_number,
                payment_date,
                amount,
                ARRAY_AGG(payment_id ORDER BY payment_id) as payment_ids
            FROM payments
            WHERE reserve_number IS NOT NULL 
            AND payment_date IS NOT NULL
            AND amount IS NOT NULL
            GROUP BY reserve_number, payment_date, amount
            HAVING COUNT(*) > 1
        )
        SELECT 
            payment_ids[2:] as ids_to_delete  -- Keep first, delete rest
        FROM duplicates
    """)
    
    to_delete = []
    for row in cur.fetchall():
        to_delete.extend(row['ids_to_delete'])
    
    print(f"Payment IDs to delete: {len(to_delete):,}")
    
    # Generate SQL
    sql_file = f"delete_payment_duplicates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    with open(sql_file, 'w') as f:
        f.write("-- DELETE DUPLICATE PAYMENTS (keep oldest by payment_id)\n")
        f.write(f"-- Count: {len(to_delete)}\n\n")
        f.write("BEGIN;\n\n")
        f.write("DELETE FROM payments WHERE payment_id IN (\n")
        f.write("  " + ", ".join(map(str, sorted(to_delete))))
        f.write("\n);\n\n")
        f.write(f"-- Expected: {len(to_delete)} rows deleted\n\n")
        f.write("COMMIT;\n")
    
    print(f"✅ SQL script saved: {sql_file}")

print()
print("=" * 80)
print("✅ Investigation complete")
print("=" * 80)

neon_conn.close()
