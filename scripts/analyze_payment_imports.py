#!/usr/bin/env python3
"""
Analyze payment_imports table (18,720 rows) and compare to payment_imports_backup.
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
print("PAYMENT_IMPORTS ANALYSIS")
print("=" * 80)

# 1. Basic counts
print("\n1. ROWCOUNT")
print("-" * 80)

cur.execute("SELECT COUNT(*) FROM payment_imports")
main_count = cur.fetchone()[0]

print(f"payment_imports: {main_count:,} rows")

# 2. Schema
print("\n2. TABLE STRUCTURE")
print("-" * 80)

cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'payment_imports'
    ORDER BY ordinal_position
""")

print("Columns:")
for col_name, col_type in cur.fetchall():
    print(f"  {col_name:30} {col_type}")

# 3. Basic statistics
print("\n3. BASIC STATISTICS")
print("-" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as total_rows,
        COUNT(DISTINCT payment_date) as unique_dates,
        MIN(payment_date) as min_date,
        MAX(payment_date) as max_date,
        SUM(amount) as total_amount,
        COUNT(DISTINCT payment_method) as unique_methods
    FROM payment_imports
""")

stats = cur.fetchone()
print(f"Total rows: {stats[0]:,}")
print(f"Unique dates: {stats[1]:,}")
print(f"Date range: {stats[2]} to {stats[3]}")
print(f"Total amount: ${stats[4]:,.2f}")
print(f"Unique payment methods: {stats[5]}")

# 4. Payment method distribution
print("\n4. PAYMENT METHOD DISTRIBUTION")
print("-" * 80)

cur.execute("""
    SELECT 
        payment_method,
        COUNT(*) as count,
        SUM(amount) as total
    FROM payment_imports
    GROUP BY payment_method
    ORDER BY COUNT(*) DESC
""")

print(f"{'Method':<30} {'Count':>10} {'Total':>18}")
print("-" * 60)
for method, count, total in cur.fetchall():
    print(f"{(method or 'NULL'):<30} {count:>10,} ${(total or 0):>15,.2f}")

# 5. Yearly breakdown
print("\n5. YEARLY BREAKDOWN")
print("-" * 80)

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM payment_date) as year,
        COUNT(*) as payments,
        SUM(amount) as total
    FROM payment_imports
    WHERE payment_date IS NOT NULL
    GROUP BY EXTRACT(YEAR FROM payment_date)
    ORDER BY year
""")

print(f"{'Year':<6} {'Payments':>10} {'Total':>18}")
print("-" * 40)
for year, count, total in cur.fetchall():
    print(f"{int(year):<6} {count:>10,} ${total:>15,.2f}")

# 6. Check against payments table
print("\n6. COMPARISON WITH PAYMENTS TABLE")
print("-" * 80)

cur.execute("SELECT COUNT(*) FROM payments")
payments_count = cur.fetchone()[0]
print(f"\npayments table: {payments_count:,} rows")

# Check for matches by date and amount
cur.execute("""
    SELECT COUNT(*) 
    FROM payment_imports pi
    JOIN payments p ON (
        pi.payment_date = p.payment_date
        AND pi.amount = p.amount
    )
""")

match_count = cur.fetchone()[0]
print(f"Matched rows (by date + amount): {match_count:,} ({match_count/main_count*100:.1f}%)")
print(f"Unmatched imports: {main_count - match_count:,}")

# 7. Sample unmatched
print("\n7. SAMPLE UNMATCHED IMPORTS (First 10)")
print("-" * 80)

cur.execute("""
    SELECT 
        pi.payment_date,
        pi.payment_method,
        pi.amount,
        pi.reference_id
    FROM payment_imports pi
    LEFT JOIN payments p ON (
        pi.payment_date = p.payment_date
        AND pi.amount = p.amount
    )
    WHERE p.payment_id IS NULL
    ORDER BY pi.payment_date
    LIMIT 10
""")

for row in cur.fetchall():
    pmt_date, method, amount, ref = row
    ref_str = (ref or 'N/A')[:20] if ref else 'N/A'
    print(f"{pmt_date} | {(method or 'N/A'):20} | ${(amount or 0):>10,.2f} | Ref: {ref_str}")

# 8. Sample data
print("\n8. SAMPLE IMPORT DATA (First 10)")
print("-" * 80)

cur.execute("""
    SELECT payment_date, payment_method, amount, reference_id, import_source
    FROM payment_imports
    ORDER BY payment_date
    LIMIT 10
""")

for row in cur.fetchall():
    pmt_date, method, amount, ref, source = row
    ref_str = (ref[:8] if ref else 'N/A').ljust(8)
    print(f"{pmt_date} | {(method or 'N/A'):15} | ${(amount or 0):>10,.2f} | Ref: {ref_str} | {(source or 'N/A')[:30]}")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("RECOMMENDATIONS")
print("=" * 80)

if match_count / main_count > 0.95:
    print("\n[COMPLETE] HIGH MATCH RATE (>95%) - DATA ALREADY PROMOTED")
    print("   The payment_imports data is already in payments table.")
    print("   Recommend: ARCHIVE payment_imports table")
elif match_count / main_count > 0.70:
    print("\n[WARNING] PARTIAL MATCH (70-95%) - SELECTIVE PROMOTION NEEDED")
    print("   Some imports are in payments table, but some are missing.")
    print("   Recommend: Promote unmatched rows to payments table")
else:
    print("\n[ACTION REQUIRED] LOW MATCH RATE (<70%) - FULL PROMOTION NEEDED")
    print("   Most payment_imports data is NOT in payments table.")
    print("   Recommend: Create full promotion script to payments table")
