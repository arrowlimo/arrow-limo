"""
Verify January 2012 database correction results.
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
print("JANUARY 2012 DATABASE VERIFICATION")
print("=" * 80)

# Get all January transactions
cur.execute("""
    SELECT 
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance,
        transaction_id
    FROM banking_transactions
    WHERE transaction_date >= '2012-01-01' AND transaction_date <= '2012-01-31'
    ORDER BY transaction_date, transaction_id
""")

txns = cur.fetchall()
print(f"\nTotal January transactions in database: {len(txns)}")

# Group by date
from collections import defaultdict
by_date = defaultdict(list)
for txn in txns:
    by_date[str(txn[0])].append(txn)

print(f"\nTransactions by date:")
print(f"{'Date':<12} {'Count':>6} {'Withdrawals':>14} {'Deposits':>14} {'Final Balance':>14}")
print("-" * 72)

for date in sorted(by_date.keys()):
    txn_list = by_date[date]
    withdrawals = sum(float(t[2] or 0) for t in txn_list)
    deposits = sum(float(t[3] or 0) for t in txn_list)
    final_balance = float(txn_list[-1][4]) if txn_list and txn_list[-1][4] is not None else 0
    print(f"{date:<12} {len(txn_list):>6} ${withdrawals:>12,.2f} ${deposits:>12,.2f} ${final_balance:>12,.2f}")

# Check for duplicates
print("\n" + "=" * 80)
print("DUPLICATE CHECK")
print("=" * 80)

cur.execute("""
    SELECT 
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance,
        COUNT(*) as dup_count
    FROM banking_transactions
    WHERE transaction_date >= '2012-01-01' AND transaction_date <= '2012-01-31'
    GROUP BY transaction_date, description, debit_amount, credit_amount, balance
    HAVING COUNT(*) > 1
    ORDER BY transaction_date, description
""")

duplicates = cur.fetchall()
if duplicates:
    print(f"\n[WARN] Found {len(duplicates)} duplicate groups:")
    print(f"\n{'Date':<12} {'Amount':>12} {'Count':>6} {'Description':<40}")
    print("-" * 80)
    for dup in duplicates[:20]:
        amount = dup[2] or dup[3]
        print(f"{dup[0]:<12} ${amount:>10,.2f} {dup[5]:>6} {dup[1][:39]}")
    if len(duplicates) > 20:
        print(f"... and {len(duplicates) - 20} more")
else:
    print("\n[OK] No duplicates found")

# Check opening balance
cur.execute("""
    SELECT transaction_date, balance, description
    FROM banking_transactions
    WHERE transaction_date = '2012-01-01'
    ORDER BY transaction_id
    LIMIT 1
""")

opening = cur.fetchone()
if opening:
    print("\n" + "=" * 80)
    print("OPENING BALANCE")
    print("=" * 80)
    print(f"\nDate: {opening[0]}")
    print(f"Balance: ${opening[1]:,.2f}")
    print(f"Description: {opening[2]}")
    print(f"Expected: $7,177.34 (from manual verification)")
    if abs(float(opening[1]) - 7177.34) < 0.01:
        print("[OK] Opening balance CORRECT")
    else:
        print(f"[WARN] Opening balance mismatch: ${abs(float(opening[1]) - 7177.34):.2f}")

# Check ending balance
cur.execute("""
    SELECT transaction_date, balance, description
    FROM banking_transactions
    WHERE transaction_date >= '2012-01-01' AND transaction_date <= '2012-01-31'
    ORDER BY transaction_date DESC, transaction_id DESC
    LIMIT 1
""")

closing = cur.fetchone()
if closing:
    print("\n" + "=" * 80)
    print("CLOSING BALANCE")
    print("=" * 80)
    print(f"\nDate: {closing[0]}")
    print(f"Balance: ${closing[1]:,.2f}")
    print(f"Description: {closing[2]}")

# Summary statistics
cur.execute("""
    SELECT 
        COUNT(*) as total_txns,
        SUM(COALESCE(debit_amount, 0)) as total_debits,
        SUM(COALESCE(credit_amount, 0)) as total_credits,
        SUM(COALESCE(debit_amount, 0)) - SUM(COALESCE(credit_amount, 0)) as net_change
    FROM banking_transactions
    WHERE transaction_date >= '2012-01-01' AND transaction_date <= '2012-01-31'
""")

stats = cur.fetchone()
print("\n" + "=" * 80)
print("SUMMARY STATISTICS")
print("=" * 80)
print(f"\nTotal transactions: {stats[0]}")
print(f"Total withdrawals: ${stats[1]:,.2f}")
print(f"Total deposits: ${stats[2]:,.2f}")
print(f"Net change: ${stats[3]:,.2f}")

# Expected from manual verification
print("\nExpected from manual verification:")
print("Total transactions: 151")
print("Total withdrawals: $54,203.83")
print("Total deposits: $46,967.32")
print("Net change: -$7,236.51")

cur.close()
conn.close()
