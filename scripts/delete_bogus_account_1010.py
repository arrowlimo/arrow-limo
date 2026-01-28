"""Delete bogus account 1010 from database after creating backup."""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REMOVED***",
    host="localhost"
)

cur = conn.cursor()

print("="*80)
print("DELETE BOGUS ACCOUNT 1010 FROM DATABASE")
print("="*80)
print()

# Analyze what we're about to delete
print("Account 1010 Analysis:")
print()

cur.execute("""
    SELECT 
        COUNT(*) as total_txns,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date,
        SUM(COALESCE(debit_amount, 0)) as total_debits,
        SUM(COALESCE(credit_amount, 0)) as total_credits,
        COUNT(DISTINCT description) as unique_descriptions
    FROM banking_transactions
    WHERE account_number = '1010'
""")

count, first, last, debits, credits, desc_count = cur.fetchone()

print(f"Total Transactions: {count:,}")
print(f"Date Range: {first} to {last}")
print(f"Total Debits: ${float(debits):,.2f}")
print(f"Total Credits: ${float(credits):,.2f}")
print(f"Unique Descriptions: {desc_count}")
print()

# Sample transactions
print("Sample Transactions (first 10):")
print()
cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount
    FROM banking_transactions
    WHERE account_number = '1010'
    ORDER BY transaction_date
    LIMIT 10
""")
print(f"{'Date':<12} {'Description':<40} {'Debit':>12} {'Credit':>12}")
print("-"*80)
for date, desc, debit, credit in cur.fetchall():
    desc = (desc or 'NaN')[:40]
    debit_str = f"${debit:,.2f}" if debit else ""
    credit_str = f"${credit:,.2f}" if credit else ""
    print(f"{date!s:<12} {desc:<40} {debit_str:>12} {credit_str:>12}")

print()
print("="*80)
print("CREATING BACKUP")
print("="*80)
print()

# Create backup table
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
backup_table = f"banking_transactions_1010_backup_{timestamp}"

cur.execute(f"""
    CREATE TABLE {backup_table} AS
    SELECT * FROM banking_transactions
    WHERE account_number = '1010'
""")

print(f"✓ Backup created: {backup_table}")
print()

# Check for foreign key references
print("="*80)
print("CHECKING FOREIGN KEY REFERENCES")
print("="*80)
print()

# Check banking_payment_links
cur.execute("""
    SELECT COUNT(*) 
    FROM banking_payment_links bpl
    JOIN banking_transactions bt ON bpl.banking_transaction_id = bt.transaction_id
    WHERE bt.account_number = '1010'
""")
payment_links = cur.fetchone()[0]

# Check banking_receipt_matching_ledger
cur.execute("""
    SELECT COUNT(*) 
    FROM banking_receipt_matching_ledger brml
    JOIN banking_transactions bt ON brml.banking_transaction_id = bt.transaction_id
    WHERE bt.account_number = '1010'
""")
receipt_links = cur.fetchone()[0]

print(f"Banking Payment Links: {payment_links:,}")
print(f"Receipt Matching Links: {receipt_links:,}")
print()

# Delete foreign key references first
if payment_links > 0:
    print(f"Deleting {payment_links:,} payment links...")
    cur.execute("""
        DELETE FROM banking_payment_links
        WHERE banking_transaction_id IN (
            SELECT transaction_id FROM banking_transactions
            WHERE account_number = '1010'
        )
    """)
    print(f"✓ Deleted {cur.rowcount:,} payment links")
    print()

if receipt_links > 0:
    print(f"Deleting {receipt_links:,} receipt matching links...")
    cur.execute("""
        DELETE FROM banking_receipt_matching_ledger
        WHERE banking_transaction_id IN (
            SELECT transaction_id FROM banking_transactions
            WHERE account_number = '1010'
        )
    """)
    print(f"✓ Deleted {cur.rowcount:,} receipt matching links")
    print()

# Delete from main table
print("="*80)
print("DELETING FROM MAIN TABLE")
print("="*80)
print()

cur.execute("DELETE FROM banking_transactions WHERE account_number = '1010'")
deleted_count = cur.rowcount

print(f"✓ Deleted {deleted_count:,} transactions from banking_transactions")
print()

# Verify deletion
cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE account_number = '1010'")
remaining = cur.fetchone()[0]

if remaining == 0:
    print("✓ Verification: No transactions remain for account 1010")
else:
    print(f"⚠️  WARNING: {remaining} transactions still exist for account 1010")

print()
print("="*80)
print("SUMMARY")
print("="*80)
print()
print(f"✓ Backed up {deleted_count:,} transactions to {backup_table}")
print(f"✓ Deleted {deleted_count:,} transactions from banking_transactions")
print(f"✓ Account 1010 removed from database")
print()

conn.commit()
cur.close()
conn.close()
