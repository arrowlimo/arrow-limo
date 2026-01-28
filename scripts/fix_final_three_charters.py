"""
Fix the final 3 charter mismatches:
- 015940: Cancel/zero out (UNCLOSED in LMS with $0)
- 015808: Cancel/zero out (CANCELLED in LMS)
- 017991: Remove incorrect $200 payment
"""

import psycopg2

pg_conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = pg_conn.cursor()

print("=" * 80)
print("FIXING FINAL 3 CHARTER MISMATCHES")
print("=" * 80)

# CHARTER 015940: Cancel/zero out
print("\nCHARTER 015940:")
print("  LMS Status: UNCLOSED with $0")
print("  PostgreSQL: $1,485 total")
print("  Solution: Mark as cancelled and zero out")

cur.execute("""
    UPDATE charters
    SET cancelled = TRUE,
        status = 'cancelled',
        total_amount_due = 0,
        paid_amount = 0,
        balance = 0
    WHERE reserve_number = '015940'
    RETURNING reserve_number, total_amount_due, paid_amount, balance
""")
result = cur.fetchone()
print(f"  [UPDATED] Reserve {result[0]}: Total=${result[1]:.2f} Paid=${result[2]:.2f} Balance=${result[3]:.2f}")

# CHARTER 015808: Cancel/zero out
print("\nCHARTER 015808:")
print("  LMS Status: CANCELLED with $0")
print("  PostgreSQL: $1,417.20 total")
print("  Solution: Mark as cancelled and zero out")

cur.execute("""
    UPDATE charters
    SET cancelled = TRUE,
        status = 'cancelled',
        total_amount_due = 0,
        paid_amount = 0,
        balance = 0
    WHERE reserve_number = '015808'
    RETURNING reserve_number, total_amount_due, paid_amount, balance
""")
result = cur.fetchone()
print(f"  [UPDATED] Reserve {result[0]}: Total=${result[1]:.2f} Paid=${result[2]:.2f} Balance=${result[3]:.2f}")

# CHARTER 017991: Remove incorrect $200 payment
print("\nCHARTER 017991:")
print("  LMS: $1,404 total, $0 paid")
print("  PostgreSQL: $200 paid")
print("  Solution: Remove the $200 payment")

# First, find the payment
cur.execute("""
    SELECT payment_id, amount, payment_key, payment_date
    FROM payments
    WHERE reserve_number = '017991'
""")
payments = cur.fetchall()
if payments:
    print(f"  Found {len(payments)} payment(s):")
    for p in payments:
        print(f"    ID {p[0]}: ${p[1]} on {p[3]} [Key: {p[2]}]")
    
    # Delete from income_ledger first (foreign key constraint)
    cur.execute("""
        DELETE FROM income_ledger
        WHERE payment_id IN (SELECT payment_id FROM payments WHERE reserve_number = '017991')
    """)
    ledger_deleted = cur.rowcount
    if ledger_deleted > 0:
        print(f"  [DELETED] {ledger_deleted} income_ledger reference(s)")
    
    # Delete all payments for this charter
    cur.execute("""
        DELETE FROM payments
        WHERE reserve_number = '017991'
        RETURNING payment_id, amount
    """)
    deleted = cur.fetchall()
    for d in deleted:
        print(f"  [DELETED] Payment ID {d[0]}: ${d[1]}")
else:
    print("  No payments found")

# Recalculate 017991
cur.execute("""
    UPDATE charters
    SET paid_amount = 0,
        balance = total_amount_due
    WHERE reserve_number = '017991'
    RETURNING total_amount_due, paid_amount, balance
""")
result = cur.fetchone()
print(f"  [UPDATED] Total=${result[0]:.2f} Paid=${result[1]:.2f} Balance=${result[2]:.2f}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("  015940: Cancelled and zeroed")
print("  015808: Cancelled and zeroed")
print("  017991: Removed incorrect payment, balance now $1,404")

response = input("\nCommit changes? (yes/no): ").strip().lower()

if response == 'yes':
    pg_conn.commit()
    print("\n[OK] Changes committed")
else:
    pg_conn.rollback()
    print("\n[CANCELLED] Changes rolled back")

cur.close()
pg_conn.close()
