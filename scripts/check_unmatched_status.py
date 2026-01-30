"""
Check current status of unmatched charters, payments, and refunds.

After all linking work, verify what still needs review.
"""

import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

print("=" * 80)
print("UNMATCHED DATA STATUS CHECK")
print("=" * 80)

conn = get_db_connection()
cur = conn.cursor()

# 1. Unmatched Payments (payments without charter linkage)
print("\n1. UNMATCHED PAYMENTS (no charter_id)")
print("-" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as unmatched_count,
        SUM(amount) as unmatched_total
    FROM payments
    WHERE reserve_number IS NULL
""")
result = cur.fetchone()
print(f"Unmatched payments: {result[0]:,}")
print(f"Unmatched amount: ${result[1]:,.2f}" if result[1] else "Unmatched amount: $0.00")

# Get sample
cur.execute("""
    SELECT payment_id, payment_date, amount, account_number, reserve_number
    FROM payments
    WHERE reserve_number IS NULL
    ORDER BY amount DESC
    LIMIT 10
""")
samples = cur.fetchall()
if samples:
    print("\nTop 10 unmatched payments by amount:")
    print(f"{'Payment ID':<12} {'Date':<12} {'Amount':<12} {'Account':<12} {'Reserve':<12}")
    print("-" * 70)
    for row in samples:
        pid = row[0]
        date = row[1].strftime('%Y-%m-%d') if row[1] else 'NULL'
        amount = float(row[2]) if row[2] else 0
        account = row[3] or 'NULL'
        reserve = row[4] or 'NULL'
        print(f"{pid:<12} {date:<12} ${amount:<11,.2f} {account:<12} {reserve:<12}")

# 2. Unlinked Refunds (refunds without charter linkage)
print("\n" + "=" * 80)
print("2. UNLINKED REFUNDS (no charter_id)")
print("-" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as unlinked_count,
        SUM(amount) as unlinked_total
    FROM charter_refunds
    WHERE reserve_number IS NULL
""")
result = cur.fetchone()
print(f"Unlinked refunds: {result[0]:,}")
print(f"Unlinked amount: ${result[1]:,.2f}" if result[1] else "Unlinked amount: $0.00")

# Get sample
cur.execute("""
    SELECT id, refund_date, amount, description, source_file
    FROM charter_refunds
    WHERE reserve_number IS NULL
    ORDER BY amount DESC
    LIMIT 10
""")
samples = cur.fetchall()
if samples:
    print("\nTop 10 unlinked refunds by amount:")
    print(f"{'ID':<8} {'Date':<12} {'Amount':<12} {'Description':<40}")
    print("-" * 80)
    for row in samples:
        rid = row[0]
        date = row[1].strftime('%Y-%m-%d') if row[1] else 'NULL'
        amount = float(row[2]) if row[2] else 0
        desc = (row[3] or '')[:37] + '...' if row[3] and len(row[3]) > 40 else (row[3] or '')
        print(f"{rid:<8} {date:<12} ${amount:<11,.2f} {desc:<40}")

# 3. Charters with no payments (balance > 0)
print("\n" + "=" * 80)
print("3. CHARTERS WITH NO PAYMENTS (balance > 0)")
print("-" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as no_payment_count,
        SUM(balance) as total_balance
    FROM charters c
    WHERE balance > 0
    AND NOT EXISTS (
        SELECT 1 FROM payments p WHERE p.charter_id = c.charter_id
    )
    AND closed = true
""")
result = cur.fetchone()
print(f"Closed charters with no payments: {result[0]:,}")
print(f"Total balance: ${result[1]:,.2f}" if result[1] else "Total balance: $0.00")

# 4. Charters with balance after payments (payment reconciliation issue)
print("\n" + "=" * 80)
print("4. CHARTERS WITH BALANCE AFTER PAYMENTS (reconciliation issues)")
print("-" * 80)

cur.execute("""
    SELECT 
        c.charter_id,
        c.reserve_number,
        c.balance,
        COALESCE(SUM(p.amount), 0) as payments_total,
        c.balance - COALESCE(SUM(p.amount), 0) as remaining_balance
    FROM charters c
    LEFT JOIN payments p ON p.charter_id = c.charter_id
    WHERE c.balance > 0 AND c.closed = true
    GROUP BY c.charter_id, c.reserve_number, c.balance
    HAVING c.balance - COALESCE(SUM(p.amount), 0) > 0.01
    ORDER BY (c.balance - COALESCE(SUM(p.amount), 0)) DESC
    LIMIT 10
""")
samples = cur.fetchall()
if samples:
    print(f"\nTop 10 charters with balance after payments:")
    print(f"{'Charter ID':<12} {'Reserve':<10} {'Balance':<12} {'Payments':<12} {'Remaining':<12}")
    print("-" * 70)
    for row in samples:
        charter_id = row[0]
        reserve = row[1] or 'NULL'
        balance = float(row[2]) if row[2] else 0
        payments = float(row[3]) if row[3] else 0
        remaining = float(row[4]) if row[4] else 0
        print(f"{charter_id:<12} {reserve:<10} ${balance:<11,.2f} ${payments:<11,.2f} ${remaining:<11,.2f}")

# 5. Refunds not accounted for in charter balance
print("\n" + "=" * 80)
print("5. REFUNDS NOT REDUCING CHARTER BALANCE")
print("-" * 80)

cur.execute("""
    SELECT 
        c.charter_id,
        c.reserve_number,
        c.balance,
        COALESCE(SUM(cr.amount), 0) as refunds_total,
        COALESCE(SUM(p.amount), 0) as payments_total
    FROM charters c
    LEFT JOIN charter_refunds cr ON cr.charter_id = c.charter_id
    LEFT JOIN payments p ON p.charter_id = c.charter_id
    WHERE cr.reserve_number IS NOT NULL
    AND c.balance > 0
    GROUP BY c.charter_id, c.reserve_number, c.balance
    HAVING COALESCE(SUM(cr.amount), 0) > 0
    ORDER BY COALESCE(SUM(cr.amount), 0) DESC
    LIMIT 10
""")
samples = cur.fetchall()
if samples:
    print(f"\nTop 10 charters with refunds but still have balance:")
    print(f"{'Charter ID':<12} {'Reserve':<10} {'Balance':<12} {'Refunds':<12} {'Payments':<12}")
    print("-" * 70)
    for row in samples:
        charter_id = row[0]
        reserve = row[1] or 'NULL'
        balance = float(row[2]) if row[2] else 0
        refunds = float(row[3]) if row[3] else 0
        payments = float(row[4]) if row[4] else 0
        print(f"{charter_id:<12} {reserve:<10} ${balance:<11,.2f} ${refunds:<11,.2f} ${payments:<11,.2f}")

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

cur.execute("SELECT COUNT(*), SUM(amount) FROM payments WHERE reserve_number IS NULL")
unmatched_payments = cur.fetchone()

cur.execute("SELECT COUNT(*), SUM(amount) FROM charter_refunds WHERE reserve_number IS NULL")
unlinked_refunds = cur.fetchone()

cur.execute("""
    SELECT COUNT(*), SUM(balance) 
    FROM charters 
    WHERE balance > 0 AND closed = true
    AND NOT EXISTS (SELECT 1 FROM payments p WHERE p.charter_id = charters.charter_id)
""")
no_payments = cur.fetchone()

print(f"\n1. Unmatched Payments: {unmatched_payments[0]:,} (${unmatched_payments[1]:,.2f})" if unmatched_payments[1] else f"\n1. Unmatched Payments: {unmatched_payments[0]:,} ($0.00)")
print(f"2. Unlinked Refunds: {unlinked_refunds[0]:,} (${unlinked_refunds[1]:,.2f})" if unlinked_refunds[1] else f"2. Unlinked Refunds: {unlinked_refunds[0]:,} ($0.00)")
print(f"3. Closed Charters with No Payments: {no_payments[0]:,} (${no_payments[1]:,.2f})" if no_payments[1] else f"3. Closed Charters with No Payments: {no_payments[0]:,} ($0.00)")

print("\n" + "=" * 80)
print("NEXT STEPS")
print("=" * 80)
print("\nBased on the results above:")
print("  1. If unmatched payments > 0: Need payment-charter linkage work")
print("  2. If unlinked refunds > 0: Need refund-charter linkage work")
print("  3. If charters with no payments: May need to import missing payment data")
print("  4. If charters with balance after payments: Need balance reconciliation")

cur.close()
conn.close()
