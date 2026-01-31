import psycopg2

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, banking_transaction_id
    FROM receipts 
    WHERE receipt_id = 45129
""")
r = cur.fetchone()

print("Receipt #45129:")
if r:
    print(f"  Date: {r[1]}")
    print(f"  Vendor: {r[2]}")
    print(f"  Amount: ${r[3]}")
    print(f"  Linked to banking: {r[4]}")
    
    # If linked, show the banking transaction
    if r[4]:
        cur.execute("""
            SELECT transaction_id, transaction_date, description, debit_amount
            FROM banking_transactions
            WHERE transaction_id = %s
        """, (r[4],))
        bt = cur.fetchone()
        if bt:
            print(f"\n  Banking Transaction:")
            print(f"    ID: {bt[0]}")
            print(f"    Date: {bt[1]}")
            print(f"    Description: {bt[2]}")
            print(f"    Amount: ${bt[3]}")
        else:
            print(f"\n  ⚠️ Banking transaction {r[4]} NOT FOUND (orphaned link)")
else:
    print("  NOT FOUND")

cur.close()
conn.close()
