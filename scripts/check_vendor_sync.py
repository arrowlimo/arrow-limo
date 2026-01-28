import psycopg2

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Find receipts linked to banking but with different vendor names
cur.execute("""
    SELECT r.receipt_id, r.vendor_name AS receipt_vendor, 
           b.description AS banking_vendor, r.gross_amount,
           r.receipt_date
    FROM receipts r 
    JOIN banking_transactions b ON r.banking_transaction_id = b.transaction_id 
    WHERE r.vendor_name != b.description 
    AND r.banking_transaction_id IS NOT NULL
    ORDER BY r.receipt_date DESC
    LIMIT 30
""")

rows = cur.fetchall()
print(f"Found receipts with mismatched vendor names:\n")
for r in rows:
    print(f"ID {r[0]} ({r[4]}): Receipt='{r[1][:30]}' vs Banking='{r[2][:30]}' (${r[3]:,.2f})")

print(f"\nTotal mismatched: {cur.rowcount}")

# Count total linked receipts
cur.execute("SELECT COUNT(*) FROM receipts WHERE banking_transaction_id IS NOT NULL")
total_linked = cur.fetchone()[0]
print(f"Total linked receipts: {total_linked:,}")

cur.close()
conn.close()
