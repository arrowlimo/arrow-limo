"""
Investigate why account 903990106011 payments aren't matching.
"""

import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

conn = get_db_connection()
cur = conn.cursor()

account = '903990106011'

print("=" * 100)
print(f"INVESTIGATING ACCOUNT: {account}")
print("=" * 100)

# Check charters for this account
print("\n1. Charters for this account:")
print("-" * 100)

cur.execute("""
    SELECT charter_id, reserve_number, charter_date, rate, balance,
           (SELECT COUNT(*) FROM payments WHERE charter_id = c.charter_id) as payment_count,
           (SELECT SUM(amount) FROM payments WHERE charter_id = c.charter_id) as total_paid
    FROM charters c
    WHERE account_number = %s
    ORDER BY charter_date DESC
    LIMIT 10
""", (account,))

charters = cur.fetchall()
if charters:
    print(f"{'Charter ID':<12} {'Reserve':<10} {'Date':<12} {'Rate':<12} {'Balance':<12} {'Pmts':<6} {'Paid':<12}")
    print("-" * 100)
    for row in charters:
        cid, reserve, date, rate, balance, pmt_count, paid = row
        date_str = date.strftime('%Y-%m-%d') if date else 'NULL'
        rate_str = f"${float(rate):,.2f}" if rate else "$0.00"
        balance_str = f"${float(balance):,.2f}" if balance else "$0.00"
        paid_str = f"${float(paid):,.2f}" if paid else "$0.00"
        print(f"{cid:<12} {reserve:<10} {date_str:<12} {rate_str:<12} {balance_str:<12} {pmt_count:<6} {paid_str:<12}")
else:
    print("No charters found!")

# Check payments for this account
print("\n2. Payments for this account:")
print("-" * 100)

cur.execute("""
    SELECT payment_id, payment_date, amount, charter_id, reserve_number, payment_method
    FROM payments
    WHERE account_number = %s
    ORDER BY payment_date DESC
    LIMIT 15
""", (account,))

payments = cur.fetchall()
if payments:
    print(f"{'Payment ID':<12} {'Date':<12} {'Amount':<12} {'Charter ID':<12} {'Reserve':<10} {'Method':<15}")
    print("-" * 100)
    for row in payments:
        pid, date, amount, charter_id, reserve, method = row
        date_str = date.strftime('%Y-%m-%d') if date else 'NULL'
        amount_str = f"${float(amount):,.2f}" if amount else "$0.00"
        charter_str = str(charter_id) if charter_id else 'NULL'
        reserve_str = reserve if reserve else 'NULL'
        method_str = method if method else 'NULL'
        print(f"{pid:<12} {date_str:<12} {amount_str:<12} {charter_str:<12} {reserve_str:<10} {method_str:<15}")
else:
    print("No payments found!")

# Check for duplicate high-value payments
print("\n3. Duplicate payment amounts (same date, same amount):")
print("-" * 100)

cur.execute("""
    SELECT payment_date, amount, COUNT(*) as count, 
           STRING_AGG(payment_id::text, ', ') as payment_ids
    FROM payments
    WHERE account_number = %s
    AND charter_id IS NULL
    GROUP BY payment_date, amount
    HAVING COUNT(*) > 1
    ORDER BY amount DESC
""", (account,))

dupes = cur.fetchall()
if dupes:
    print(f"{'Date':<12} {'Amount':<12} {'Count':<8} {'Payment IDs':<40}")
    print("-" * 100)
    for date, amount, count, pids in dupes:
        date_str = date.strftime('%Y-%m-%d') if date else 'NULL'
        amount_str = f"${float(amount):,.2f}" if amount else "$0.00"
        print(f"{date_str:<12} {amount_str:<12} {count:<8} {pids:<40}")
else:
    print("No duplicate payments found")

# Check if this is a 2012 QBO duplicate issue
print("\n4. Payment source analysis:")
print("-" * 100)

cur.execute("""
    SELECT 
        CASE 
            WHEN payment_key LIKE 'QBO%' THEN 'QuickBooks'
            WHEN payment_key LIKE 'LMS%' THEN 'LMS'
            WHEN payment_key LIKE 'BTX%' THEN 'Banking'
            WHEN square_payment_id IS NOT NULL THEN 'Square'
            ELSE 'Unknown'
        END as source,
        COUNT(*) as count,
        COUNT(CASE WHEN charter_id IS NULL THEN 1 END) as unmatched
    FROM payments
    WHERE account_number = %s
    GROUP BY source
    ORDER BY count DESC
""", (account,))

sources = cur.fetchall()
if sources:
    print(f"{'Source':<20} {'Total':<10} {'Unmatched':<10}")
    print("-" * 40)
    for source, count, unmatched in sources:
        print(f"{source:<20} {count:<10} {unmatched:<10}")

cur.close()
conn.close()

print("\n" + "=" * 100)
print("ANALYSIS COMPLETE")
print("=" * 100)
