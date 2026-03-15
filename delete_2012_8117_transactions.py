#!/usr/bin/env python3
"""
DELETE all 2012 transactions from CIBC account 8117 (3648117)
WARNING: This will permanently remove 60 transactions from the database
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='ArrowLimousine'
)

cur = conn.cursor()

print("=" * 100)
print("DELETE 2012 CIBC ACCOUNT 8117 (3648117) TRANSACTIONS")
print("=" * 100)

# First, show what will be deleted
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        receipt_id,
        reconciliation_status
    FROM banking_transactions
    WHERE account_number = '3648117'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_date
""")

transactions_to_delete = cur.fetchall()

print(f"\n⚠️  WARNING: About to delete {len(transactions_to_delete)} transactions\n")
print(f"{'ID':<8} | {'Date':<12} | {'Debit':>12} | {'Credit':>12} | {'Receipt':<8} | {'Description'[:40]}")
print("-" * 100)

for txn in transactions_to_delete:
    txn_id, date, desc, debit, credit, receipt_id, status = txn
    debit_str = f"${debit:,.2f}" if debit and debit > 0 else ""
    credit_str = f"${credit:,.2f}" if credit and credit > 0 else ""
    receipt_str = str(receipt_id) if receipt_id else ""
    desc_short = desc[:40] if desc else ""
    
    print(f"{txn_id:<8} | {str(date):<12} | {debit_str:>12} | {credit_str:>12} | {receipt_str:<8} | {desc_short}")

print("\n" + "=" * 100)

# Check for linked receipts
cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions
    WHERE account_number = '3648117'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    AND receipt_id IS NOT NULL
""")

linked_receipts = cur.fetchone()[0]

if linked_receipts > 0:
    print(f"\n⚠️  WARNING: {linked_receipts} of these transactions are linked to receipts!")
    print("    Deleting these will orphan the receipts (receipts will remain but lose banking link)")

print("\n" + "=" * 100)
print("PROCEED WITH DELETION?")
print("=" * 100)
print("\nType 'DELETE ALL 2012 8117' (exactly) to confirm deletion, or anything else to cancel:")

confirmation = input("> ").strip()

if confirmation == "DELETE ALL 2012 8117":
    print("\n🗑️  Deleting transactions...")
    
    # Delete the transactions
    cur.execute("""
        DELETE FROM banking_transactions
        WHERE account_number = '3648117'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
    """)
    
    deleted_count = cur.rowcount
    
    # Commit the deletion
    conn.commit()
    
    print(f"\n✅ Successfully deleted {deleted_count} transactions from account 8117 (2012)")
    print("\nDeletion complete!")
    
else:
    print("\n❌ CANCELLED - No transactions were deleted")
    print(f"   You entered: '{confirmation}'")
    print(f"   Expected: 'DELETE ALL 2012 8117'")

cur.close()
conn.close()
