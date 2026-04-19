"""
Check receipt 145289 (CHQ 197 balance $457.25) - is it linked? Is there a split?
"""
import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

# Check if receipt 145289 is linked to any banking txn
cur.execute("""
    SELECT rbl.link_id, rbl.transaction_id, rbl.linked_amount, rbl.link_status,
           bt.transaction_date, bt.debit_amount, bt.description
    FROM receipt_banking_links rbl
    JOIN banking_transactions bt ON bt.transaction_id = rbl.transaction_id
    WHERE rbl.receipt_id = 145289
""")
rows = cur.fetchall()
print("Links for receipt 145289:")
for r in rows:
    print(f"  link_id={r[0]} bt_id={r[1]} linked_amt={r[2]} status={r[3]} date={r[4]} debit={r[5]} desc={r[6]}")
if not rows:
    print("  (none)")

# Check all receipts near Jan 3 2012 for 106.7 The Drive acct (id=12)
cur.execute("""
    SELECT r.receipt_id, r.receipt_date, r.gross_amount, r.description, r.receipt_source,
           rbl.transaction_id, rbl.linked_amount
    FROM receipts r
    LEFT JOIN receipt_banking_links rbl ON rbl.receipt_id = r.receipt_id
    WHERE r.vendor_account_id = 12
    AND r.receipt_date >= '2011-12-01' AND r.receipt_date <= '2012-02-28'
    ORDER BY r.receipt_date, r.receipt_id
""")
rows = cur.fetchall()
print("\nAll 106.7 The Drive (acct 12) receipts Dec2011-Feb2012:")
for r in rows:
    print(f"  receipt_id={r[0]} date={r[1]} amt={r[2]} desc={r[3][:60] if r[3] else ''} bt_id={r[5]} linked_amt={r[6]}")

# The $550 cheque - CHQ 197 - check any other receipts mentioning CHQ 197
cur.execute("""
    SELECT r.receipt_id, r.receipt_date, r.gross_amount, r.description, r.vendor_name, r.vendor_account_id,
           rbl.transaction_id
    FROM receipts r
    LEFT JOIN receipt_banking_links rbl ON rbl.receipt_id = r.receipt_id
    WHERE r.description ILIKE '%chq 197%' OR r.description ILIKE '%chq197%'
    ORDER BY r.receipt_date
""")
rows = cur.fetchall()
print("\nAll receipts mentioning CHQ 197:")
for r in rows:
    print(f"  receipt_id={r[0]} date={r[1]} amt={r[2]} vendor={r[4]} desc={r[3][:70] if r[3] else ''} bt_id={r[6]}")

conn.close()
