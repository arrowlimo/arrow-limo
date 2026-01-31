"""
Check if Square payments have last 4 digits in square_last4 column.
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
print("SQUARE PAYMENT LAST 4 DIGITS AVAILABILITY")
print("=" * 80)

conn = get_db_connection()
cur = conn.cursor()

# Check square_last4 for all payments
print("\n1. Square Last 4 in Payments Table")
print("-" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as total_payments,
        COUNT(square_payment_id) as with_square_id,
        COUNT(square_last4) as with_square_last4,
        COUNT(CASE WHEN square_last4 IS NOT NULL AND square_last4 != '' THEN 1 END) as non_empty_last4
    FROM payments
""")

stats = cur.fetchone()
print(f"Total payments: {stats[0]:,}")
print(f"With square_payment_id: {stats[1]:,} ({stats[1]/stats[0]*100:.1f}%)")
print(f"With square_last4 (not null): {stats[2]:,} ({stats[2]/stats[0]*100:.1f}%)")
print(f"With square_last4 (not empty): {stats[3]:,} ({stats[3]/stats[0]*100:.1f}%)")

# Check for UNMATCHED payments with Square data
print("\n2. Unmatched Payments with Square Data")
print("-" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as total_unmatched,
        COUNT(square_payment_id) as with_square_id,
        COUNT(square_last4) as with_square_last4,
        COUNT(CASE WHEN square_last4 IS NOT NULL AND square_last4 != '' THEN 1 END) as non_empty_last4
    FROM payments
    WHERE reserve_number IS NULL
""")

unmatched = cur.fetchone()
print(f"Total unmatched: {unmatched[0]:,}")
print(f"With square_payment_id: {unmatched[1]:,} ({unmatched[1]/unmatched[0]*100:.1f}%)")
print(f"With square_last4 (not null): {unmatched[2]:,} ({unmatched[2]/unmatched[0]*100:.1f}%)")
print(f"With square_last4 (not empty): {unmatched[3]:,} ({unmatched[3]/unmatched[0]*100:.1f}%)")

# Sample Square payments with last 4
print("\n3. Sample Square Payments with Last 4 Digits")
print("-" * 80)

cur.execute("""
    SELECT payment_id, payment_date, amount, square_payment_id, square_last4, 
           square_card_brand, charter_id IS NOT NULL as is_matched
    FROM payments
    WHERE square_last4 IS NOT NULL AND square_last4 != ''
    ORDER BY payment_date DESC
    LIMIT 10
""")

samples = cur.fetchall()
if samples:
    print(f"\n{'Payment ID':<12} {'Date':<12} {'Amount':<12} {'Square ID':<25} {'Last4':<8} {'Brand':<12} {'Matched?':<10}")
    print("-" * 105)
    for row in samples:
        pid, date, amount, square_id, last4, brand, matched = row
        date_str = date.strftime('%Y-%m-%d') if date else 'NULL'
        square_id_str = (square_id[:22] + '...') if square_id and len(square_id) > 22 else (square_id or 'NULL')
        last4_str = last4 or 'NULL'
        brand_str = brand or 'NULL'
        matched_str = 'YES' if matched else 'NO'
        print(f"{pid:<12} {date_str:<12} ${float(amount):<11,.2f} {square_id_str:<25} {last4_str:<8} {brand_str:<12} {matched_str:<10}")
else:
    print("No Square payments with last 4 digits found.")

# Check unmatched Square payments with last 4
print("\n4. Unmatched Square Payments with Last 4 Digits")
print("-" * 80)

cur.execute("""
    SELECT payment_id, payment_date, amount, square_payment_id, square_last4, 
           square_card_brand, account_number
    FROM payments
    WHERE reserve_number IS NULL
    AND square_last4 IS NOT NULL AND square_last4 != ''
    ORDER BY amount DESC
    LIMIT 15
""")

unmatched_samples = cur.fetchall()
if unmatched_samples:
    print(f"\n{'Payment ID':<12} {'Date':<12} {'Amount':<12} {'Square ID':<25} {'Last4':<8} {'Brand':<12} {'Account':<15}")
    print("-" * 115)
    for row in unmatched_samples:
        pid, date, amount, square_id, last4, brand, account = row
        date_str = date.strftime('%Y-%m-%d') if date else 'NULL'
        amount_str = f"${float(amount):,.2f}" if amount is not None else "$0.00"
        square_id_str = (square_id[:22] + '...') if square_id and len(square_id) > 22 else (square_id or 'NULL')
        last4_str = last4 or 'NULL'
        brand_str = brand or 'NULL'
        account_str = account or 'NULL'
        print(f"{pid:<12} {date_str:<12} {amount_str:<12} {square_id_str:<25} {last4_str:<8} {brand_str:<12} {account_str:<15}")
    
    print(f"\n✓ Found {len(unmatched_samples)} unmatched payments with Square last 4 digits!")
    print("  These can potentially be matched using:")
    print("  1. Account number + date + amount")
    print("  2. Square last 4 for disambiguation when multiple charters match")
else:
    print("No unmatched Square payments with last 4 digits found.")

# Check distinct last 4 values
print("\n5. Square Last 4 Value Distribution")
print("-" * 80)

cur.execute("""
    SELECT square_last4, COUNT(*) as count
    FROM payments
    WHERE square_last4 IS NOT NULL AND square_last4 != ''
    GROUP BY square_last4
    ORDER BY count DESC
    LIMIT 15
""")

last4_dist = cur.fetchall()
if last4_dist:
    print(f"\n{'Last 4':<10} {'Payment Count':<15}")
    print("-" * 25)
    for last4, count in last4_dist:
        print(f"{last4:<10} {count:<15,}")
    print(f"\nTotal unique last 4 values: {len(last4_dist)}")
else:
    print("No last 4 values found.")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)
print("""
If Square payments have last 4 digits in square_last4 column:
✓ Can use for payment-charter matching disambiguation
✓ When multiple charters match on account+date+amount, use last 4 to pick correct one
✓ Especially useful for customers with multiple runs on same day
""")
