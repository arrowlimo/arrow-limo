#!/usr/bin/env python3
"""
Delete the 2 extra transactions not in the bank CSV.
Transaction IDs: 55604 (2018-02-06, $520.93), 55596 (2018-07-09, $1921.28)
"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Get transaction details before deletion
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount
    FROM banking_transactions
    WHERE transaction_id IN (55604, 55596)
    ORDER BY transaction_date
""")

to_delete = cur.fetchall()

print("DELETING THE FOLLOWING TRANSACTIONS NOT IN BANK CSV:")
print()
print(f"{'ID':<8} {'Date':<12} {'Amount':>12} {'Description':<50}")
print("-" * 82)

for txn_id, date, desc, debit, credit in to_delete:
    amt = debit if debit else credit
    print(f"{txn_id:<8} {date:<12} ${amt:>11.2f} {desc:<48}")

print()

# Delete them
cur.execute("DELETE FROM banking_transactions WHERE transaction_id IN (55604, 55596)")
deleted_count = cur.rowcount

conn.commit()
cur.close()
conn.close()

print("=" * 82)
print(f"✅ Successfully deleted {deleted_count} transactions")
print("=" * 82)
