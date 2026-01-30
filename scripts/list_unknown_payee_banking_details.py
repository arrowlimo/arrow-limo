import psycopg2

VENDOR = 'UNKNOWN PAYEE'
BATCH = 10

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

cur.execute(
    """
    SELECT COUNT(*) FROM receipts WHERE vendor_name = %s
    """,
    (VENDOR,),
)
count = cur.fetchone()[0]
print(f"Total UNKNOWN PAYEE receipts: {count}")

cur.execute(
    """
    SELECT receipt_id, receipt_date, gross_amount, banking_transaction_id
    FROM receipts
    WHERE vendor_name = %s
    ORDER BY receipt_date, receipt_id
    """,
    (VENDOR,),
)
rows = cur.fetchall()

# We'll fetch banking description from banking_transactions.transaction_id
bt_ids = [r[3] for r in rows if r[3] is not None]
desc_map = {}
if bt_ids:
    cur.execute(
        """
        SELECT transaction_id, description
        FROM banking_transactions
        WHERE transaction_id = ANY(%s)
        """,
        (bt_ids,),
    )
    desc_map = {row[0]: row[1] for row in cur.fetchall()}

# Print in batches of 10
print("\nDetails in batches of 10 (date, amount, bank_txn_id, bank description):")
for i in range(0, len(rows), BATCH):
    chunk = rows[i:i+BATCH]
    print(f"\nBatch {i//BATCH + 1}:")
    for r in chunk:
        rid, rdate, amt, btid = r
        desc = desc_map.get(btid, '') if btid else ''
        print(f"  ID {rid:<8} {rdate}  ${amt:>11,.2f}  BTID {str(btid or 'NULL'):<8}  {desc}")

cur.close(); conn.close()
