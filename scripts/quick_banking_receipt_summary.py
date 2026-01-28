import psycopg2

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='***REMOVED***', host='localhost')
cur = conn.cursor()

print("\n=== SUMMARY OF BANKING TRANSACTIONS NEEDING RECEIPTS ===\n")

# Check if receipt_id exists
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'banking_transactions' AND column_name = 'receipt_id'")
has_receipt_id = cur.fetchone() is not None

print(f"banking_transactions has receipt_id column: {has_receipt_id}")
print()

# Total banking expenses
cur.execute("SELECT COUNT(*), SUM(debit_amount) FROM banking_transactions WHERE debit_amount > 0")
total_count, total_amount = cur.fetchone()
print(f"Total banking expense transactions: {total_count:,}")
print(f"Total amount: ${total_amount:,.2f}")
print()

# Categories needing receipts
categories = {
    "Banking Fees": "description ILIKE '%fee%' OR description ILIKE '%charge%'",
    "E-Transfers": "description ILIKE '%e-transfer%' OR description ILIKE '%etransfer%' OR description ILIKE '%interac%'",
    "ATM Withdrawals": "description ILIKE '%atm%' OR description ILIKE '%withdrawal%' OR description ILIKE '%cash%'",
    "Transfers": "description ILIKE '%transfer%'",
    "Credit Card": "description ILIKE '%visa%' OR description ILIKE '%mastercard%'",
    "Money Mart": "description ILIKE '%money mart%'",
    "Heffner": "description ILIKE '%heffner%'",
    "Rent": "description ILIKE '%rent%'",
    "Utilities": "description ILIKE '%telus%' OR description ILIKE '%shaw%' OR description ILIKE '%bell%'",
}

print("Categories without receipts:\n")
for name, condition in categories.items():
    cur.execute(f"SELECT COUNT(*), COALESCE(SUM(debit_amount), 0) FROM banking_transactions WHERE debit_amount > 0 AND ({condition})")
    count, amount = cur.fetchone()
    if count > 0:
        print(f"  {name:20} {count:6,} txns    ${amount:12,.2f}")

print("\n" + "="*70)
print("BOTTOM LINE:")
print("="*70)
print(f"\nNO banking transactions currently have receipts linked.")
print(f"Need to:")
print(f"  1. Add receipt_id column to banking_transactions")
print(f"  2. Create receipts for all {total_count:,} transactions")
print(f"  3. Link transactions to receipts")
print(f"\nTotal value needing receipts: ${total_amount:,.2f}")

cur.close()
conn.close()
