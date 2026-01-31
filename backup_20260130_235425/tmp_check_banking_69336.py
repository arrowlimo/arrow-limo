import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

print("Banking transaction 69336:\n")

cur.execute("SELECT * FROM banking_transactions WHERE transaction_id = 69336")
result = cur.fetchone()

if result:
    # Get column names
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'banking_transactions' ORDER BY ordinal_position")
    cols = [row[0] for row in cur.fetchall()]
    
    print(f"Columns: {cols}\n")
    for i, col in enumerate(cols):
        print(f"{col}: {result[i]}")
else:
    print("No banking transaction found with ID 69336")

print("\n" + "=" * 70)
print("All receipts linked to banking transaction 69336:")
print("=" * 70 + "\n")

cur.execute("SELECT receipt_id, receipt_date, vendor_name, gross_amount FROM receipts WHERE banking_transaction_id = 69336 ORDER BY receipt_id")
rows = cur.fetchall()

total = 0
for r_id, r_date, r_vendor, r_amount in rows:
    print(f"ID {r_id} | {r_date} | {r_vendor:20s} | ${r_amount:8.2f}")
    total += float(r_amount) if r_amount else 0

print(f"\nTotal of all receipts linked to 69336: ${total:.2f}")

cur.close()
conn.close()
