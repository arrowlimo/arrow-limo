"""
Check if #140690 is a receipt_id, and look at the full fuel split situation for bt 94814.
"""
import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

# Check receipt 140690
cur.execute("""
    SELECT r.receipt_id, r.receipt_date, r.gross_amount, r.vendor_name, r.description,
           r.vendor_account_id, va.canonical_vendor,
           rbl.transaction_id, rbl.linked_amount
    FROM receipts r
    LEFT JOIN vendor_accounts va ON va.account_id = r.vendor_account_id
    LEFT JOIN receipt_banking_links rbl ON rbl.receipt_id = r.receipt_id
    WHERE r.receipt_id = 140690
""")
r = cur.fetchone()
if r:
    print(f"Receipt 140690: date={r[1]} amt={r[2]} vendor={r[3]} canonical={r[6]}")
    print(f"  desc: {r[4]}")
    print(f"  linked to bt: {r[7]} linked_amt={r[8]}")
else:
    print("Receipt 140690: NOT FOUND")

# Also search for any receipts around Sept 2012 with fuel/centex descriptions near $120
cur.execute("""
    SELECT r.receipt_id, r.receipt_date, r.gross_amount, r.vendor_name, r.description,
           rbl.transaction_id
    FROM receipts r
    LEFT JOIN receipt_banking_links rbl ON rbl.receipt_id = r.receipt_id
    WHERE r.receipt_date BETWEEN '2012-09-15' AND '2012-10-05'
    AND (r.vendor_name ILIKE '%fuel%' OR r.vendor_name ILIKE '%centex%' OR r.vendor_name ILIKE '%fas gas%'
         OR r.description ILIKE '%fuel%' OR r.description ILIKE '%L-7%' OR r.description ILIKE '%103.54%')
    ORDER BY r.receipt_date
""")
rows = cur.fetchall()
print("\nFuel receipts Sep-Oct 2012:")
for row in rows:
    print(f"  receipt {row[0]} date={row[1]} amt={row[2]} vendor={row[3]} bt={row[5]} desc={str(row[4])[:60]}")

# Also check all receipts near receipt_id 140690 (say 140685-140695)
cur.execute("""
    SELECT r.receipt_id, r.receipt_date, r.gross_amount, r.vendor_name, r.description,
           rbl.transaction_id
    FROM receipts r
    LEFT JOIN receipt_banking_links rbl ON rbl.receipt_id = r.receipt_id
    WHERE r.receipt_id BETWEEN 140685 AND 140700
    ORDER BY r.receipt_id
""")
rows = cur.fetchall()
print("\nReceipts id 140685-140700:")
for row in rows:
    print(f"  receipt {row[0]} date={row[1]} amt={row[2]} vendor={row[3]} bt={row[5]} desc={str(row[4])[:60]}")

conn.close()
