"""Analyze charters with unmatched payments."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 80)
print("CHARTER PAYMENT MATCHING ANALYSIS")
print("=" * 80)

# 1. Payments with NULL charter_id
print("\n1. PAYMENTS WITH NULL CHARTER_ID")
print("-" * 80)
cur.execute("""
    SELECT 
        COUNT(*) as payment_count,
        SUM(amount) as total_amount,
        MIN(payment_date) as earliest_date,
        MAX(payment_date) as latest_date
    FROM payments
    WHERE charter_id IS NULL
""")
null_charter = cur.fetchone()
print(f"Payments without charter_id: {null_charter[0]:,}")
print(f"Total amount: ${null_charter[1]:,.2f}" if null_charter[1] else "Total amount: $0.00")
print(f"Date range: {null_charter[2]} to {null_charter[3]}")

# 2. Payments with NULL charter_id but have reserve_number
print("\n2. PAYMENTS WITH RESERVE_NUMBER BUT NULL CHARTER_ID")
print("-" * 80)
cur.execute("""
    SELECT 
        COUNT(*) as payment_count,
        SUM(amount) as total_amount
    FROM payments
    WHERE charter_id IS NULL
    AND reserve_number IS NOT NULL
    AND reserve_number != ''
""")
with_reserve = cur.fetchone()
print(f"Payments with reserve_number but no charter_id: {with_reserve[0]:,}")
print(f"Total amount: ${with_reserve[1]:,.2f}" if with_reserve[1] else "Total amount: $0.00")

# 3. Sample payments with reserve_number but no charter match
print("\n3. SAMPLE UNMATCHED PAYMENTS (with reserve_number)")
print("-" * 80)
cur.execute("""
    SELECT 
        p.payment_id,
        p.reserve_number,
        p.payment_date,
        p.amount,
        p.payment_method,
        p.payment_key,
        CASE 
            WHEN EXISTS (
                SELECT 1 FROM charters c 
                WHERE c.reserve_number = p.reserve_number
            ) THEN 'Charter EXISTS'
            ELSE 'No matching charter'
        END as charter_status
    FROM payments p
    WHERE p.reserve_number IS NULL
    AND p.reserve_number IS NOT NULL
    AND p.reserve_number != ''
    ORDER BY p.payment_date DESC
    LIMIT 20
""")
print(f"{'Payment ID':<12} {'Reserve#':<10} {'Date':<12} {'Amount':<12} {'Method':<15} {'Status':<20}")
print("-" * 80)
for row in cur.fetchall():
    print(f"{row[0]:<12} {row[1]:<10} {str(row[2]):<12} ${row[3]:<11,.2f} {(row[4] or 'N/A')[:14]:<15} {row[6]:<20}")

# 4. Charters with balance but no payments linked
print("\n4. CHARTERS WITH BALANCE BUT NO PAYMENT LINKAGE")
print("-" * 80)
cur.execute("""
    SELECT 
        COUNT(*) as charter_count,
        SUM(balance) as total_balance
    FROM charters
    WHERE charter_id NOT IN (
        SELECT DISTINCT charter_id 
        FROM payments 
        WHERE charter_id IS NOT NULL
    )
    AND balance != 0
    AND status NOT IN ('cancelled', 'Cancelled')
""")
unlinked = cur.fetchone()
print(f"Charters with balance but no linked payments: {unlinked[0]:,}")
print(f"Total balance: ${unlinked[1]:,.2f}" if unlinked[1] else "Total balance: $0.00")

# 5. Sample charters with balance but no payment links
print("\n5. SAMPLE CHARTERS WITH BALANCE (no payment links)")
print("-" * 80)
cur.execute("""
    SELECT 
        c.charter_id,
        c.reserve_number,
        c.charter_date,
        c.balance,
        c.status,
        (SELECT COUNT(*) 
         FROM payments p 
         WHERE p.reserve_number = c.reserve_number) as payment_count
    FROM charters c
    WHERE c.charter_id NOT IN (
        SELECT DISTINCT charter_id 
        FROM payments 
        WHERE charter_id IS NOT NULL
    )
    AND c.balance != 0
    AND c.status NOT IN ('cancelled', 'Cancelled')
    ORDER BY c.charter_date DESC
    LIMIT 20
""")
print(f"{'Charter ID':<12} {'Reserve#':<10} {'Date':<12} {'Balance':<12} {'Status':<15} {'Payments':<10}")
print("-" * 80)
for row in cur.fetchall():
    print(f"{row[0]:<12} {row[1]:<10} {str(row[2]):<12} ${row[3]:<11,.2f} {(row[4] or 'N/A')[:14]:<15} {row[5]:<10}")

# 6. Payment matching statistics
print("\n6. OVERALL PAYMENT MATCHING STATISTICS")
print("-" * 80)
cur.execute("""
    SELECT 
        COUNT(*) as total_payments,
        COUNT(charter_id) as matched_payments,
        COUNT(*) - COUNT(charter_id) as unmatched_payments,
        SUM(amount) as total_amount,
        SUM(CASE WHEN charter_id IS NOT NULL THEN amount ELSE 0 END) as matched_amount,
        SUM(CASE WHEN charter_id IS NULL THEN amount ELSE 0 END) as unmatched_amount
    FROM payments
    WHERE payment_date >= '2007-01-01'
    AND payment_date <= '2024-12-31'
""")
stats = cur.fetchone()
print(f"Total payments (2007-2024): {stats[0]:,}")
print(f"Matched payments: {stats[1]:,} ({stats[1]/stats[0]*100:.1f}%)")
print(f"Unmatched payments: {stats[2]:,} ({stats[2]/stats[0]*100:.1f}%)")
print(f"\nTotal amount: ${stats[3]:,.2f}")
print(f"Matched amount: ${stats[4]:,.2f} ({stats[4]/stats[3]*100:.1f}%)")
print(f"Unmatched amount: ${stats[5]:,.2f} ({stats[5]/stats[3]*100:.1f}%)")

# 7. Unmatched payments by year
print("\n7. UNMATCHED PAYMENTS BY YEAR")
print("-" * 80)
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM payment_date) as year,
        COUNT(*) as payment_count,
        SUM(amount) as total_amount
    FROM payments
    WHERE charter_id IS NULL
    AND payment_date IS NOT NULL
    GROUP BY EXTRACT(YEAR FROM payment_date)
    ORDER BY year
""")
print(f"{'Year':<8} {'Count':<10} {'Amount':<15}")
print("-" * 80)
for row in cur.fetchall():
    print(f"{int(row[0]):<8} {row[1]:<10,} ${row[2]:>13,.2f}")

print("\n" + "=" * 80)

cur.close()
conn.close()
