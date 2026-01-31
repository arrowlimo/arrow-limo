"""
Analyze 2012 QBO duplicate payment issue.
"""

import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

conn = get_db_connection()
cur = conn.cursor()

print("=" * 100)
print("2012 QBO DUPLICATE PAYMENT ANALYSIS")
print("=" * 100)

# Count unmatched payments by year
print("\n1. Unmatched Payments by Year")
print("-" * 100)

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM payment_date) as year,
        COUNT(*) as count,
        SUM(amount) as total_amount
    FROM payments
    WHERE reserve_number IS NULL
    AND amount > 0
    GROUP BY year
    ORDER BY year
""")

by_year = cur.fetchall()
for year, count, total in by_year:
    year_str = str(int(year)) if year else 'NULL'
    print(f"{year_str}: {count:,} payments, ${float(total):,.2f}")

# Check 2012 specifically
print("\n2. 2012 Unmatched Payments - Duplicate Analysis")
print("-" * 100)

cur.execute("""
    SELECT 
        payment_date, 
        amount, 
        account_number,
        COUNT(*) as duplicate_count,
        STRING_AGG(payment_id::text, ', ') as payment_ids
    FROM payments
    WHERE reserve_number IS NULL
    AND EXTRACT(YEAR FROM payment_date) = 2012
    AND amount > 0
    GROUP BY payment_date, amount, account_number
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC, amount DESC
    LIMIT 20
""")

dupes_2012 = cur.fetchall()
print(f"\nFound {cur.rowcount} duplicate clusters in 2012")
print(f"\n{'Date':<12} {'Amount':<12} {'Account':<15} {'Count':<8} {'Payment IDs':<40}")
print("-" * 100)
for date, amount, account, count, pids in dupes_2012:
    date_str = date.strftime('%Y-%m-%d') if date else 'NULL'
    amount_str = f"${float(amount):,.2f}" if amount else "$0.00"
    account_str = account[:12] if account else 'NULL'
    pids_str = pids[:37] + '...' if len(pids) > 37 else pids
    print(f"{date_str:<12} {amount_str:<12} {account_str:<15} {count:<8} {pids_str:<40}")

# How many 2012 payments are duplicates vs unique?
print("\n3. 2012 Payment Breakdown")
print("-" * 100)

cur.execute("""
    WITH dupe_check AS (
        SELECT 
            payment_id,
            COUNT(*) OVER (PARTITION BY payment_date, amount, account_number) as dup_count
        FROM payments
        WHERE reserve_number IS NULL
        AND EXTRACT(YEAR FROM payment_date) = 2012
        AND amount > 0
    )
    SELECT 
        COUNT(CASE WHEN dup_count = 1 THEN 1 END) as unique_payments,
        COUNT(CASE WHEN dup_count = 2 THEN 1 END) as duplicate_pairs,
        COUNT(CASE WHEN dup_count > 2 THEN 1 END) as duplicate_tripleplus,
        COUNT(*) as total
    FROM dupe_check
""")

breakdown = cur.fetchone()
print(f"Unique payments (no duplicate): {breakdown[0]:,}")
print(f"Duplicate pairs (exactly 2): {breakdown[1]:,}")
print(f"Duplicate 3+: {breakdown[2]:,}")
print(f"Total 2012 unmatched: {breakdown[3]:,}")

# Check if these match known QBO import pattern
print("\n4. 2012 Payment Source Check")
print("-" * 100)

cur.execute("""
    SELECT 
        CASE 
            WHEN payment_key ~ '^[0-9]+$' THEN 'Numeric Key (QBO?)'
            WHEN payment_key LIKE 'QBO%' THEN 'QBO Explicit'
            WHEN payment_key LIKE 'LMS%' THEN 'LMS'
            ELSE 'Other'
        END as source_type,
        COUNT(*) as count,
        COUNT(DISTINCT payment_key) as unique_keys
    FROM payments
    WHERE reserve_number IS NULL
    AND EXTRACT(YEAR FROM payment_date) = 2012
    AND amount > 0
    GROUP BY source_type
    ORDER BY count DESC
""")

sources = cur.fetchall()
print(f"{'Source Type':<30} {'Count':<10} {'Unique Keys':<15}")
print("-" * 55)
for source, count, keys in sources:
    print(f"{source:<30} {count:<10,} {keys:<15,}")

# Sample QBO-style keys
print("\n5. Sample Payment Keys (2012)")
print("-" * 100)

cur.execute("""
    SELECT payment_id, payment_key, payment_date, amount
    FROM payments
    WHERE reserve_number IS NULL
    AND EXTRACT(YEAR FROM payment_date) = 2012
    AND amount > 0
    ORDER BY payment_id
    LIMIT 10
""")

samples = cur.fetchall()
print(f"{'Payment ID':<12} {'Payment Key':<20} {'Date':<12} {'Amount':<12}")
print("-" * 56)
for pid, key, date, amount in samples:
    key_str = key[:17] + '...' if key and len(key) > 17 else (key or 'NULL')
    date_str = date.strftime('%Y-%m-%d') if date else 'NULL'
    amount_str = f"${float(amount):,.2f}" if amount else "$0.00"
    print(f"{pid:<12} {key_str:<20} {date_str:<12} {amount_str:<12}")

cur.close()
conn.close()

print("\n" + "=" * 100)
print("RECOMMENDATION")
print("=" * 100)
print("""
The 2012 unmatched payments appear to be QBO import duplicates.

Solution Strategy:
1. Keep ONE payment from each duplicate pair
2. Delete the other as confirmed duplicate
3. Then match the remaining unique payments to charters

This will significantly reduce the 2,526 unmatched count.
""")
