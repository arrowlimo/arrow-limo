#!/usr/bin/env python3
"""Delete the two suspicious 2012 banking transactions (no source recorded)."""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("=" * 100)
print("DELETE SUSPICIOUS 2012 BANKING TRANSACTIONS")
print("=" * 100 + "\n")

# Get transaction details
transactions_to_delete = [60389, 60330]

print("Transactions to delete:\n")
for trans_id in transactions_to_delete:
    cur.execute("""
        SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, locked
        FROM banking_transactions
        WHERE transaction_id = %s
    """, (trans_id,))
    
    result = cur.fetchone()
    if result:
        tid, date, desc, debit, credit, locked = result
        amount = debit or credit
        print(f"Transaction {tid}")
        print(f"  Date: {date}")
        print(f"  Desc: {desc}")
        print(f"  Amount: ${amount:,.2f}")
        print(f"  Locked: {locked}")
        print()

# Check if they're locked
print("Unlocking transactions...")
for trans_id in transactions_to_delete:
    cur.execute("""
        UPDATE banking_transactions
        SET locked = FALSE
        WHERE transaction_id = %s
    """, (trans_id,))
    print(f"  Unlocked transaction {trans_id}")

conn.commit()

# Delete the receipts that reference these transactions
print("\nDeleting associated receipts...")
for trans_id in transactions_to_delete:
    cur.execute("""
        DELETE FROM receipts
        WHERE banking_transaction_id = %s
    """, (trans_id,))
    deleted = cur.rowcount
    if deleted > 0:
        print(f"  Deleted {deleted} receipt(s) linked to transaction {trans_id}")

conn.commit()

# Delete the banking transactions
print("\nDeleting banking transactions...")
for trans_id in transactions_to_delete:
    cur.execute("""
        DELETE FROM banking_transactions
        WHERE transaction_id = %s
    """, (trans_id,))
    deleted = cur.rowcount
    print(f"  Deleted transaction {trans_id}")

conn.commit()

# Verify deletion
print("\nVerifying deletion...")
cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE transaction_id IN (60389, 60330)")
remaining = cur.fetchone()[0]

if remaining == 0:
    print("✅ Both transactions successfully deleted")
else:
    print(f"❌ ERROR: {remaining} transactions still exist")

print("\n" + "=" * 100)
print("DELETION COMPLETE")
print("=" * 100)

cur.close()
conn.close()
