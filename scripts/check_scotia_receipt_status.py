"""Check Scotia banking transaction receipt status."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("Scotia Bank Account 903990106011 Status:\n")

cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE account_number='903990106011'")
print(f"Total Scotia transactions: {cur.fetchone()[0]}")

cur.execute("""
    SELECT COUNT(DISTINCT bt.transaction_id) 
    FROM banking_transactions bt 
    JOIN banking_receipt_matching_ledger bm ON bt.transaction_id = bm.banking_transaction_id 
    WHERE bt.account_number='903990106011'
""")
print(f"Scotia with receipts linked: {cur.fetchone()[0]}")

cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions bt 
    WHERE account_number='903990106011' 
    AND debit_amount > 0 
    AND NOT EXISTS (
        SELECT 1 FROM banking_receipt_matching_ledger bm 
        WHERE bm.banking_transaction_id = bt.transaction_id
    )
""")
unmatched = cur.fetchone()[0]
print(f"Scotia debits WITHOUT receipts: {unmatched}")

conn.close()
