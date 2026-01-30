"""Analyze unmatched payment patterns and reasons."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("=" * 80)
print("UNMATCHED PAYMENT DEEP ANALYSIS")
print("=" * 80)

# 1. Unmatched payments by payment_key pattern
print("\n1. UNMATCHED PAYMENTS BY KEY PATTERN")
print("-" * 80)
cur.execute("""
    SELECT 
        CASE 
            WHEN payment_key LIKE 'BTX:%' THEN 'Interac e-Transfer (BTX)'
            WHEN payment_key LIKE 'LMSDEP:%' THEN 'LMS Deposit'
            WHEN payment_key LIKE 'QBO:%' THEN 'QuickBooks Online'
            WHEN payment_key LIKE 'SQ:%' THEN 'Square'
            WHEN payment_key ~ '^[0-9]+$' THEN 'Numeric Key'
            WHEN payment_key IS NULL THEN 'NULL Key'
            ELSE 'Other Pattern'
        END as key_type,
        COUNT(*) as payment_count,
        SUM(amount) as total_amount
    FROM payments
    WHERE reserve_number IS NULL
    AND payment_date >= '2007-01-01'
    AND payment_date <= '2024-12-31'
    GROUP BY key_type
    ORDER BY payment_count DESC
""")
print(f"{'Key Pattern':<30} {'Count':<10} {'Amount':<15}")
print("-" * 80)
for row in cur.fetchall():
    print(f"{row[0]:<30} {row[1]:<10,} ${row[2]:>13,.2f}")

# 2. Sample Interac e-Transfers
print("\n2. SAMPLE INTERAC E-TRANSFERS (BTX)")
print("-" * 80)
cur.execute("""
    SELECT 
        p.payment_id,
        p.payment_key,
        p.payment_date,
        p.amount,
        p.notes
    FROM payments p
    WHERE p.reserve_number IS NULL
    AND p.payment_key LIKE 'BTX:%'
    ORDER BY p.payment_date DESC
    LIMIT 15
""")
print(f"{'Payment ID':<12} {'Key':<20} {'Date':<12} {'Amount':<12} {'Notes':<30}")
print("-" * 80)
for row in cur.fetchall():
    notes = (row[4] or '')[:28]
    print(f"{row[0]:<12} {row[1]:<20} {str(row[2]):<12} ${row[3]:<11,.2f} {notes:<30}")

# 3. Sample LMS Deposits
print("\n3. SAMPLE LMS DEPOSITS (LMSDEP)")
print("-" * 80)
cur.execute("""
    SELECT 
        p.payment_id,
        p.payment_key,
        p.payment_date,
        p.amount,
        p.notes
    FROM payments p
    WHERE p.reserve_number IS NULL
    AND p.payment_key LIKE 'LMSDEP:%'
    ORDER BY p.payment_date DESC
    LIMIT 15
""")
print(f"{'Payment ID':<12} {'Key':<25} {'Date':<12} {'Amount':<12} {'Notes':<25}")
print("-" * 80)
for row in cur.fetchall():
    notes = (row[4] or '')[:23]
    print(f"{row[0]:<12} {row[1]:<25} {str(row[2]):<12} ${row[3]:<11,.2f} {notes:<25}")

# 4. Large unmatched payments (>$500)
print("\n4. LARGE UNMATCHED PAYMENTS (>$500)")
print("-" * 80)
cur.execute("""
    SELECT 
        p.payment_id,
        p.payment_key,
        p.payment_date,
        p.amount,
        p.account_number,
        p.notes
    FROM payments p
    WHERE p.reserve_number IS NULL
    AND p.payment_date >= '2007-01-01'
    AND p.payment_date <= '2024-12-31'
    AND p.amount > 500
    ORDER BY p.amount DESC
    LIMIT 20
""")
print(f"{'Payment ID':<12} {'Key':<20} {'Date':<12} {'Amount':<12} {'Account#':<12} {'Notes':<20}")
print("-" * 80)
for row in cur.fetchall():
    key = (row[1] or 'N/A')[:18]
    acct = (row[4] or 'N/A')[:10]
    notes = (row[5] or '')[:18]
    print(f"{row[0]:<12} {key:<20} {str(row[2]):<12} ${row[3]:<11,.2f} {acct:<12} {notes:<20}")

# 5. Negative unmatched payments (refunds/reversals)
print("\n5. NEGATIVE UNMATCHED PAYMENTS (Refunds/Reversals)")
print("-" * 80)
cur.execute("""
    SELECT 
        COUNT(*) as payment_count,
        SUM(amount) as total_amount,
        MIN(amount) as min_amount,
        MAX(amount) as max_amount
    FROM payments
    WHERE reserve_number IS NULL
    AND amount < 0
    AND payment_date >= '2007-01-01'
    AND payment_date <= '2024-12-31'
""")
neg = cur.fetchone()
print(f"Negative payments: {neg[0]:,}")
print(f"Total amount: ${neg[1]:,.2f}")
print(f"Range: ${neg[2]:,.2f} to ${neg[3]:,.2f}")

# 6. Account numbers with most unmatched payments
print("\n6. TOP ACCOUNTS WITH UNMATCHED PAYMENTS")
print("-" * 80)
cur.execute("""
    SELECT 
        account_number,
        COUNT(*) as payment_count,
        SUM(amount) as total_amount
    FROM payments
    WHERE reserve_number IS NULL
    AND account_number IS NOT NULL
    AND payment_date >= '2007-01-01'
    AND payment_date <= '2024-12-31'
    GROUP BY account_number
    ORDER BY payment_count DESC
    LIMIT 15
""")
print(f"{'Account#':<15} {'Count':<10} {'Amount':<15}")
print("-" * 80)
for row in cur.fetchall():
    print(f"{row[0]:<15} {row[1]:<10,} ${row[2]:>13,.2f}")

# 7. Check if account numbers exist in charters
print("\n7. UNMATCHED PAYMENTS WHERE ACCOUNT EXISTS IN CHARTERS")
print("-" * 80)
cur.execute("""
    SELECT 
        COUNT(DISTINCT p.payment_id) as unmatched_payments,
        SUM(p.amount) as total_amount
    FROM payments p
    WHERE p.reserve_number IS NULL
    AND p.account_number IS NOT NULL
    AND EXISTS (
        SELECT 1 FROM charters c 
        WHERE c.account_number = p.account_number
    )
    AND p.payment_date >= '2007-01-01'
    AND p.payment_date <= '2024-12-31'
""")
exists = cur.fetchone()
print(f"Unmatched payments with existing account: {exists[0]:,}")
print(f"Total amount: ${exists[1]:,.2f}" if exists[1] else "Total amount: $0.00")

# 8. 2012 QBO import issues
print("\n8. 2012 QBO IMPORT ANALYSIS")
print("-" * 80)
cur.execute("""
    SELECT 
        COUNT(*) as payment_count,
        SUM(amount) as total_amount,
        COUNT(CASE WHEN payment_key LIKE 'QBO:%' THEN 1 END) as qbo_count
    FROM payments
    WHERE reserve_number IS NULL
    AND EXTRACT(YEAR FROM payment_date) = 2012
""")
qbo = cur.fetchone()
print(f"Total 2012 unmatched: {qbo[0]:,}")
print(f"Total amount: ${qbo[1]:,.2f}")
print(f"QBO-keyed payments: {qbo[2]:,}")

print("\n" + "=" * 80)

cur.close()
conn.close()
