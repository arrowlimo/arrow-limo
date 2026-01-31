import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

# Query the specific IDs we found
ids = [145322, 145323, 140662]

print("=" * 70)
print("Receipts 145322, 145323, 140662 (the $4, $36.01, $94.99)")
print("=" * 70 + "\n")

for rid in ids:
    cur.execute("SELECT receipt_id, receipt_date, vendor_name, gross_amount, parent_receipt_id, banking_transaction_id FROM receipts WHERE receipt_id = %s", (rid,))
    result = cur.fetchone()
    if result:
        r_id, r_date, r_vendor, r_amount, r_parent, r_banking = result
        parent_info = f"Parent: {r_parent}" if r_parent else "No parent"
        banking_info = f"Banking: {r_banking}" if r_banking else "No banking link"
        print(f"ID {r_id} | {r_date} | ${r_amount:.2f} | {parent_info} | {banking_info}")

# Now search for the parent with $135
print("\n" + "=" * 70)
print("Looking for parent receipt of $135:")
print("=" * 70 + "\n")

cur.execute("SELECT receipt_id, receipt_date, gross_amount, banking_transaction_id FROM receipts WHERE vendor_name ILIKE '%RUN''N ON EMPTY%' AND EXTRACT(YEAR FROM receipt_date) = 2012 AND gross_amount > 120 AND gross_amount < 140")
rows = cur.fetchall()
for r_id, r_date, r_amount, r_banking in rows:
    print(f"ID {r_id} | {r_date} | ${r_amount:.2f} | Banking: {r_banking}")

cur.close()
conn.close()
