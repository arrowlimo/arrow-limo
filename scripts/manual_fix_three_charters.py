"""
Fix the 3 remaining charter mismatches with manual corrections.
"""

import psycopg2

pg_conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)

cur = pg_conn.cursor()

print("=" * 80)
print("MANUAL FIXES FOR 3 CHARTERS")
print("=" * 80)

# CHARTER 016086: Remove duplicate $84 payment (keep LMS version, remove ETR version)
print("\nCHARTER 016086:")
print("  Problem: Duplicate $84 payment - ETR:32797 ($83.16) vs LMS:20849 ($84.00)")
print("  Solution: Delete the ETR version (ID 100170)")

cur.execute("""
    DELETE FROM payments 
    WHERE payment_id = 100170 
    AND payment_key = 'ETR:32797' 
    AND reserve_number = '016086'
    RETURNING payment_id, amount, payment_key
""")
deleted = cur.fetchone()
if deleted:
    print(f"  [DELETED] Payment ID {deleted[0]}: ${deleted[1]} ({deleted[2]})")

# Recalculate 016086
cur.execute("""
    UPDATE charters
    SET paid_amount = (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE reserve_number = '016086'),
        balance = total_amount_due - (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE reserve_number = '016086')
    WHERE reserve_number = '016086'
    RETURNING total_amount_due, paid_amount, balance
""")
result = cur.fetchone()
print(f"  [UPDATED] Total=${result[0]:.2f} Paid=${result[1]:.2f} Balance=${result[2]:.2f}")

# CHARTER 013690: Import missing $1,240 payment
print("\nCHARTER 013690:")
print("  Problem: Missing payment PaymentID 16375 ($1,240)")
print("  Solution: Import from LMS")

cur.execute("""
    INSERT INTO payments (reserve_number, payment_key, payment_date, amount, last_updated_by, created_at)
    VALUES ('013690', 'LMS:16375', '2018-06-04', 1240.00, 'manual_fix_three_charters.py', CURRENT_TIMESTAMP)
    RETURNING payment_id, amount
""")
inserted = cur.fetchone()
print(f"  [IMPORTED] Payment ID {inserted[0]}: ${inserted[1]}")

# Recalculate 013690
cur.execute("""
    UPDATE charters
    SET paid_amount = (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE reserve_number = '013690'),
        balance = total_amount_due - (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE reserve_number = '013690')
    WHERE reserve_number = '013690'
    RETURNING total_amount_due, paid_amount, balance
""")
result = cur.fetchone()
print(f"  [UPDATED] Total=${result[0]:.2f} Paid=${result[1]:.2f} Balance=${result[2]:.2f}")

# CHARTER 017720: Import 10 missing $102 payments
print("\nCHARTER 017720:")
print("  Problem: Missing 10 x $102 payments (PaymentIDs 22203-22212)")
print("  Solution: Import from LMS")

missing_payments = [
    (22203, '2023-07-04'),
    (22204, '2023-07-04'),
    (22205, '2023-07-04'),
    (22206, '2023-07-04'),
    (22207, '2023-07-04'),
    (22208, '2023-07-04'),
    (22209, '2023-07-04'),
    (22210, '2023-07-04'),
    (22211, '2023-07-04'),
    (22212, '2023-07-04'),
]

imported_count = 0
for payment_id, date in missing_payments:
    cur.execute("""
        INSERT INTO payments (reserve_number, payment_key, payment_date, amount, last_updated_by, created_at)
        VALUES ('017720', %s, %s, 102.00, 'manual_fix_three_charters.py', CURRENT_TIMESTAMP)
        RETURNING payment_id
    """, (f'LMS:{payment_id}', date))
    new_id = cur.fetchone()[0]
    imported_count += 1
    print(f"  [IMPORTED] Payment ID {new_id}: $102.00 (LMS:{payment_id})")

# Recalculate 017720
cur.execute("""
    UPDATE charters
    SET paid_amount = (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE reserve_number = '017720'),
        balance = total_amount_due - (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE reserve_number = '017720')
    WHERE reserve_number = '017720'
    RETURNING total_amount_due, paid_amount, balance
""")
result = cur.fetchone()
print(f"  [UPDATED] Total=${result[0]:.2f} Paid=${result[1]:.2f} Balance=${result[2]:.2f}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("  016086: Removed duplicate $83.16 payment")
print("  013690: Imported missing $1,240 payment")
print(f"  017720: Imported {imported_count} missing $102 payments")

response = input("\nCommit changes? (yes/no): ").strip().lower()

if response == 'yes':
    pg_conn.commit()
    print("\n[OK] Changes committed")
else:
    pg_conn.rollback()
    print("\n[CANCELLED] Changes rolled back")

cur.close()
pg_conn.close()
