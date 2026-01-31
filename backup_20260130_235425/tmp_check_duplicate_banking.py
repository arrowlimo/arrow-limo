import psycopg2

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

# Get both transactions
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, account_number
    FROM banking_transactions 
    WHERE transaction_id IN (45176, 45798)
    ORDER BY transaction_id
""")
rows = cur.fetchall()

print("Banking Transactions Comparison:")
print("=" * 80)
for r in rows:
    print(f"\nTransaction ID: {r[0]}")
    print(f"  Date: {r[1]}")
    print(f"  Description: {r[2]}")
    print(f"  Debit: ${r[3]}")
    print(f"  Credit: ${r[4]}")
    print(f"  Account: {r[5]}")

if len(rows) == 2:
    print("\n" + "=" * 80)
    print("COMPARISON:")
    print(f"  Same date? {rows[0][1] == rows[1][1]}")
    print(f"  Same description? {rows[0][2] == rows[1][2]}")
    print(f"  Same debit amount? {rows[0][3] == rows[1][3]}")
    print(f"  Same account? {rows[0][5] == rows[1][5]}")
    
    if all([rows[0][1] == rows[1][1], rows[0][2] == rows[1][2], rows[0][3] == rows[1][3]]):
        print("\n✅ These appear to be DUPLICATES")
    else:
        print("\n❌ These are DIFFERENT transactions")

# Check what's linked
print("\n" + "=" * 80)
print("LINKED RECEIPTS:")
for txn_id in [45176, 45798]:
    cur.execute("SELECT COUNT(*) FROM receipts WHERE banking_transaction_id = %s", (txn_id,))
    count = cur.fetchone()[0]
    print(f"  Transaction {txn_id}: {count} receipt(s) linked via receipts.banking_transaction_id")
    
cur.close()
conn.close()
