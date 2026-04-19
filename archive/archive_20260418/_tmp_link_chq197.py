"""
Link receipt 145289 ($457.25, 106.7 The Drive) to bt 101807 (CHQ 197, $550, 2012-01-03)
as a partial link — remainder was applied to invoice.
"""
import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

RECEIPT_ID = 145289
BT_ID = 101807
LINKED_AMOUNT = 457.25

# Verify
cur.execute("SELECT receipt_id, receipt_date, gross_amount, description FROM receipts WHERE receipt_id=%s", (RECEIPT_ID,))
r = cur.fetchone()
print(f"Receipt: id={r[0]} date={r[1]} amt={r[2]} desc={r[3]}")

cur.execute("SELECT transaction_id, transaction_date, debit_amount, description FROM banking_transactions WHERE transaction_id=%s", (BT_ID,))
r = cur.fetchone()
print(f"Banking: id={r[0]} date={r[1]} debit={r[2]} desc={r[3]}")

# Insert link
cur.execute("""
    INSERT INTO receipt_banking_links
        (receipt_id, transaction_id, linked_amount, link_status, linked_by, linked_at, notes)
    VALUES (%s, %s, %s, 'partial', NULL, NOW(), 'CHQ 197 $550 total; $457.25 to receipt, $92.75 to invoice credit')
""", (RECEIPT_ID, BT_ID, LINKED_AMOUNT))

conn.commit()
print(f"\nLinked receipt {RECEIPT_ID} -> bt {BT_ID} for ${LINKED_AMOUNT} (partial)")
conn.close()
