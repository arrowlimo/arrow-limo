#!/usr/bin/env python3
"""
Delete all 2012 transactions from CIBC account 8117 (3648117)
User has confirmed deletion - executing directly
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='ArrowLimousine'
)

cur = conn.cursor()

# First show what we're deleting
cur.execute("""
    SELECT 
        COUNT(*),
        COUNT(DISTINCT receipt_id) FILTER (WHERE receipt_id IS NOT NULL) as receipts_linked,
        SUM(debit_amount) FILTER (WHERE debit_amount IS NOT NULL) as total_debits,
        SUM(credit_amount) FILTER (WHERE credit_amount IS NOT NULL) as total_credits
    FROM banking_transactions
    WHERE account_number = '3648117'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
""")

count, receipts, debits, credits = cur.fetchone()

print("=" * 80)
print("DELETING 2012 CIBC ACCOUNT 8117 TRANSACTIONS")
print("=" * 80)
print(f"\nTransactions to delete: {count}")
print(f"Linked receipts (will be orphaned): {receipts}")
print(f"Total debits: ${debits:,.2f}")
print(f"Total credits: ${credits:,.2f}")
print(f"Net: ${(credits - debits):,.2f}")

# Delete the transactions
cur.execute("""
    DELETE FROM banking_transactions
    WHERE account_number = '3648117'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
""")

deleted = cur.rowcount

# Commit the changes
conn.commit()

print(f"\n✅ Successfully deleted {deleted} transactions from 2012")

# Verify deletion
cur.execute("""
    SELECT COUNT(*)
    FROM banking_transactions
    WHERE account_number = '3648117'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
""")

remaining = cur.fetchone()[0]
print(f"✅ Verified: {remaining} transactions remaining in 2012 (should be 0)")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("DELETION COMPLETE")
print("=" * 80)
