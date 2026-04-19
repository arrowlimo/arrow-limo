"""
Re-link receipt 140690 from bt 69364 (Scotia 9039) -> bt 94814 (1615 account).
"""
import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

# Show before state
cur.execute("SELECT link_id, receipt_id, transaction_id, linked_amount, link_status FROM receipt_banking_links WHERE receipt_id=140690")
print("BEFORE - links for receipt 140690:")
for r in cur.fetchall():
    print(f"  link_id={r[0]} bt={r[2]} linked_amt={r[3]} status={r[4]}")

# Delete the wrong link (receipt 140690 -> bt 69364)
cur.execute("DELETE FROM receipt_banking_links WHERE receipt_id=140690 AND transaction_id=69364")
deleted = cur.rowcount
print(f"\nDeleted {deleted} row(s) (receipt 140690 -> bt 69364)")

# Insert correct link (receipt 140690 -> bt 94814)
cur.execute("""
    INSERT INTO receipt_banking_links
        (receipt_id, transaction_id, linked_amount, link_status, linked_at, notes)
    VALUES (140690, 94814, 120.00, 'matched', NOW(),
            'Re-linked from bt 69364 (Scotia) to bt 94814 (1615) - correct account for this split')
""")
print(f"Inserted new link: receipt 140690 -> bt 94814 ($120.00)")

conn.commit()

# Show after state
cur.execute("SELECT link_id, receipt_id, transaction_id, linked_amount, link_status FROM receipt_banking_links WHERE receipt_id=140690")
print("\nAFTER - links for receipt 140690:")
for r in cur.fetchall():
    print(f"  link_id={r[0]} bt={r[2]} linked_amt={r[3]} status={r[4]}")

# Also confirm bt 94814 is now linked
cur.execute("""
    SELECT rbl.receipt_id, rbl.linked_amount, r.vendor_name, r.description
    FROM receipt_banking_links rbl JOIN receipts r ON r.receipt_id=rbl.receipt_id
    WHERE rbl.transaction_id=94814
""")
print("\nbt 94814 links after fix:")
for r in cur.fetchall():
    print(f"  receipt {r[0]} ${r[1]} vendor={r[2]} desc={str(r[3])[:60]}")

conn.close()
