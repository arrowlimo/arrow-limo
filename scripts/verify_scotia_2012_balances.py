#!/usr/bin/env python
"""
Verify Scotia 2012 (903990106011) balances against user-provided checkpoints.
These are the verified statement balances from yesterday.
"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

print("=" * 100)
print("SCOTIA 2012 (903990106011) BALANCE VERIFICATION")
print("=" * 100)

# User-provided verified balances from statement
VERIFIED_CHECKPOINTS = [
    ("2012-01-01", 40.00, "Opening balance"),
    ("2012-02-22", 140.00, "February 22 checkpoint"),
    ("2012-02-29", 91.00, "February 29 close"),
    ("2012-04-02", 0.00, "April 2 checkpoint"),
    ("2012-04-09", 200.00, "April 9 checkpoint"),
    ("2012-04-30", 266.00, "April 30 close"),
    ("2012-05-18", 181.77, "May 18 checkpoint"),
    ("2012-06-22", 156.76, "June 22 checkpoint"),
    ("2012-06-25", 5317.51, "June 25 checkpoint (multiple deposits)"),
    ("2012-06-29", 4195.89, "June 29 close"),
    ("2012-07-06", 2323.28, "July 6 checkpoint"),
    ("2012-07-12", 3214.39, "July 12 close"),
]

print("\nVerified Statement Balances vs Database:")
print("-" * 100)

all_match = True
for check_date, expected_balance, label in VERIFIED_CHECKPOINTS:
    # Get last balance recorded on or before this date
    cur.execute("""
        SELECT balance FROM banking_transactions
        WHERE account_number = '903990106011'
        AND transaction_date <= %s
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        ORDER BY transaction_date DESC, transaction_id DESC
        LIMIT 1
    """, (check_date,))
    
    result = cur.fetchone()
    
    if result:
        actual = float(result[0])
        diff = actual - expected_balance
        match = abs(diff) < 0.01
        
        status = "✓" if match else "✗"
        if not match:
            all_match = False
        
        print(f"{status} {check_date} | {label:35s} | Expected: ${expected_balance:10,.2f} | Got: ${actual:10,.2f} | Diff: ${diff:+10,.2f}")
    else:
        print(f"✗ {check_date} | {label:35s} | NO DATA FOUND")
        all_match = False

print("\n" + "=" * 100)

# Check opening and closing dates
cur.execute("""
    SELECT MIN(transaction_date), MAX(transaction_date)
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
""")
min_date, max_date = cur.fetchone()

print(f"Date Range Coverage:")
print(f"  First transaction: {min_date}")
print(f"  Last transaction: {max_date}")

# Get first and last balances
cur.execute("""
    SELECT balance FROM banking_transactions
    WHERE account_number = '903990106011'
    AND transaction_date = %s
    ORDER BY transaction_id LIMIT 1
""", (min_date,))
first_balance = cur.fetchone()[0]

cur.execute("""
    SELECT balance FROM banking_transactions
    WHERE account_number = '903990106011'
    AND transaction_date = %s
    ORDER BY transaction_id DESC LIMIT 1
""", (max_date,))
last_balance = cur.fetchone()[0]

print(f"  First balance recorded: ${first_balance:,.2f}")
print(f"  Last balance recorded: ${last_balance:,.2f}")

print("\n" + "=" * 100)
if all_match:
    print("✓ ALL VERIFIED BALANCES MATCH DATABASE!")
    print("Scotia 2012 data has been successfully restored from verified statement.")
else:
    print("✗ SOME BALANCES DO NOT MATCH")
    print("There may be data gaps or discrepancies that need investigation.")

print("=" * 100)

cur.close()
conn.close()
