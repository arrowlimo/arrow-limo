"""
Check February 2012 opening and closing balances.
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("=" * 80)
print("FEBRUARY 2012 BALANCE VERIFICATION")
print("=" * 80)

# Check Feb 1 opening
cur.execute("""
    SELECT transaction_date, description, balance
    FROM banking_transactions
    WHERE transaction_date = '2012-02-01'
    ORDER BY transaction_id
    LIMIT 1
""")

feb1 = cur.fetchone()

if feb1:
    print(f"\nFeb 1 Opening Transaction:")
    print(f"  Date: {feb1[0]}")
    print(f"  Description: {feb1[1]}")
    balance = float(feb1[2]) if feb1[2] is not None else 0.0
    print(f"  Balance: ${balance:,.2f}")
    print(f"  Expected: $-49.17 (Jan 31 closing)")
    if abs(balance - (-49.17)) < 0.01:
        print(f"  Status: [OK] MATCH")
    else:
        print(f"  Status: [WARN] MISMATCH (Δ ${abs(balance - (-49.17)):.2f})")
else:
    print("\n[WARN] No Feb 1 transaction found")

# Check Feb 29 closing (2012 was a leap year)
cur.execute("""
    SELECT transaction_date, description, balance
    FROM banking_transactions
    WHERE transaction_date = '2012-02-29'
    ORDER BY transaction_id DESC
    LIMIT 1
""")

feb29 = cur.fetchone()

if feb29:
    print(f"\nFeb 29 Closing Transaction:")
    print(f"  Date: {feb29[0]}")
    print(f"  Description: {feb29[1]}")
    balance = float(feb29[2]) if feb29[2] is not None else 0.0
    print(f"  Balance: ${balance:,.2f}")
    print(f"  Expected: $1,014.49")
    if abs(balance - 1014.49) < 0.01:
        print(f"  Status: [OK] MATCH")
    else:
        print(f"  Status: [WARN] MISMATCH (Δ ${abs(balance - 1014.49):.2f})")
else:
    print("\n[WARN] No Feb 29 transaction found")

# Get February transaction count
cur.execute("""
    SELECT COUNT(*)
    FROM banking_transactions
    WHERE transaction_date >= '2012-02-01' AND transaction_date <= '2012-02-29'
""")

feb_count = cur.fetchone()[0]
print(f"\nTotal February transactions in database: {feb_count}")

# Get first and last transactions of February
cur.execute("""
    SELECT transaction_date, description, balance
    FROM banking_transactions
    WHERE transaction_date >= '2012-02-01' AND transaction_date <= '2012-02-29'
    ORDER BY transaction_date, transaction_id
    LIMIT 1
""")

first_feb = cur.fetchone()

cur.execute("""
    SELECT transaction_date, description, balance
    FROM banking_transactions
    WHERE transaction_date >= '2012-02-01' AND transaction_date <= '2012-02-29'
    ORDER BY transaction_date DESC, transaction_id DESC
    LIMIT 1
""")

last_feb = cur.fetchone()

print("\n" + "=" * 80)
print("FEBRUARY 2012 DATABASE BOUNDARIES")
print("=" * 80)
print(f"\nFirst transaction:")
print(f"  Date: {first_feb[0]}")
print(f"  Description: {first_feb[1]}")
balance_first = float(first_feb[2]) if first_feb[2] is not None else 0.0
print(f"  Balance: ${balance_first:,.2f}")

print(f"\nLast transaction:")
print(f"  Date: {last_feb[0]}")
print(f"  Description: {last_feb[1]}")
balance_last = float(last_feb[2]) if last_feb[2] is not None else 0.0
print(f"  Balance: ${balance_last:,.2f}")

# Validation summary
print("\n" + "=" * 80)
print("VALIDATION SUMMARY")
print("=" * 80)

feb1_balance = float(feb1[2]) if feb1 and feb1[2] is not None else None
feb29_balance = float(feb29[2]) if feb29 and feb29[2] is not None else None

opening_ok = feb1_balance is not None and abs(feb1_balance - (-49.17)) < 0.01
closing_ok = feb29_balance is not None and abs(feb29_balance - 1014.49) < 0.01

print(f"\n{'Check':<40} {'Status':<20}")
print("-" * 60)
print(f"{'Feb 1 opening = -$49.17':<40} {'[OK] PASS' if opening_ok else '[FAIL] FAIL'}")
print(f"{'Feb 29 closing = $1,014.49':<40} {'[OK] PASS' if closing_ok else '[FAIL] FAIL'}")

if opening_ok and closing_ok:
    print("\n[OK] FEBRUARY 2012 BOUNDARIES: VERIFIED")
else:
    print("\n[WARN] Some checks failed - review above")

cur.close()
conn.close()
