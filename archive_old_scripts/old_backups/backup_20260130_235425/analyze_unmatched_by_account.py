"""
Analyze unmatched payments by account number to identify problematic accounts.
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
print("UNMATCHED PAYMENTS BY ACCOUNT NUMBER")
print("=" * 100)

# Top accounts with unmatched payments
print("\n1. Top Accounts with Unmatched Payments")
print("-" * 100)

cur.execute("""
    SELECT 
        account_number,
        COUNT(*) as payment_count,
        SUM(amount) as total_amount,
        MIN(payment_date) as first_payment,
        MAX(payment_date) as last_payment
    FROM payments
    WHERE reserve_number IS NULL
    AND account_number IS NOT NULL
    AND amount > 0
    GROUP BY account_number
    ORDER BY COUNT(*) DESC
    LIMIT 20
""")

accounts = cur.fetchall()
print(f"\n{'Account':<15} {'Count':<8} {'Total Amount':<15} {'First':<12} {'Last':<12}")
print("-" * 72)
for account, count, total, first, last in accounts:
    account_str = account[:12] if account else 'NULL'
    total_str = f"${float(total):,.2f}" if total else "$0.00"
    first_str = first.strftime('%Y-%m-%d') if first else 'NULL'
    last_str = last.strftime('%Y-%m-%d') if last else 'NULL'
    print(f"{account_str:<15} {count:<8} {total_str:<15} {first_str:<12} {last_str:<12}")

# Check if account 903990106011 has any charters
print("\n2. Charter Check for Top Accounts")
print("-" * 100)

cur.execute("""
    WITH top_accounts AS (
        SELECT 
            account_number,
            COUNT(*) as payment_count
        FROM payments
        WHERE reserve_number IS NULL
        AND account_number IS NOT NULL
        AND amount > 0
        GROUP BY account_number
        ORDER BY COUNT(*) DESC
        LIMIT 10
    )
    SELECT 
        ta.account_number,
        ta.payment_count,
        COUNT(c.charter_id) as charter_count
    FROM top_accounts ta
    LEFT JOIN charters c ON c.account_number = ta.account_number
    GROUP BY ta.account_number, ta.payment_count
    ORDER BY ta.payment_count DESC
""")

charter_check = cur.fetchall()
print(f"\n{'Account':<15} {'Unmatch Pmts':<15} {'Charters':<12}")
print("-" * 42)
for account, pmt_count, charter_count in charter_check:
    account_str = account[:12] if account else 'NULL'
    print(f"{account_str:<15} {pmt_count:<15} {charter_count:<12}")

# How many unmatched payments have NO account number?
print("\n3. Payments with No Account Number")
print("-" * 100)

cur.execute("""
    SELECT 
        COUNT(*) as no_account_count,
        SUM(amount) as total_amount,
        COUNT(CASE WHEN reserve_number IS NOT NULL THEN 1 END) as with_reserve,
        COUNT(CASE WHEN square_payment_id IS NOT NULL THEN 1 END) as with_square
    FROM payments
    WHERE reserve_number IS NULL
    AND account_number IS NULL
    AND amount > 0
""")

no_account = cur.fetchone()
print(f"Payments with no account number: {no_account[0]:,}")
print(f"Total amount: ${float(no_account[1]):,.2f}")
print(f"  With reserve_number: {no_account[2]:,}")
print(f"  With square_payment_id: {no_account[3]:,}")

# Summary
print("\n" + "=" * 100)
print("SUMMARY & RECOMMENDATIONS")
print("=" * 100)

# Get total unmatched
cur.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(amount) as total_amount,
        COUNT(CASE WHEN account_number = '903990106011' THEN 1 END) as bogus_account,
        SUM(CASE WHEN account_number = '903990106011' THEN amount ELSE 0 END) as bogus_amount
    FROM payments
    WHERE reserve_number IS NULL
    AND amount > 0
""")

summary = cur.fetchone()
print(f"\nTotal unmatched payments (amount > 0): {summary[0]:,}")
print(f"Total amount: ${float(summary[1]):,.2f}")
print(f"\nAccount 903990106011 (no charters exist):")
print(f"  Payments: {summary[2]:,} ({summary[2]/summary[0]*100:.1f}% of unmatched)")
print(f"  Amount: ${float(summary[3]):,.2f} ({summary[3]/summary[1]*100:.1f}% of amount)")

print(f"\nRECOMMENDATION:")
print(f"  Account 903990106011 appears to be invalid (no charters exist)")
print(f"  These {summary[2]} payments should be:")
print(f"    1. Marked as 'external_system' or 'invalid_account'")
print(f"    2. Excluded from charter matching")
print(f"    3. Reviewed for potential deletion or migration to separate table")

cur.close()
conn.close()
