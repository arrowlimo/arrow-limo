"""
Test split receipt detection - find and display all splits based on banking_transaction links
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("\n" + "="*80)
print("SPLIT RECEIPT DETECTION TEST - Banking Transaction Linking")
print("="*80)

# Find all transactions that have MULTIPLE receipts linked
cur.execute("""
    SELECT transaction_id, COUNT(DISTINCT receipt_id) as receipt_count
    FROM receipt_banking_links
    GROUP BY transaction_id
    HAVING COUNT(DISTINCT receipt_id) > 1
    ORDER BY receipt_count DESC, transaction_id DESC
""")

splits = cur.fetchall()
print(f"\n✅ Found {len(splits)} banking transactions with MULTIPLE receipts (i.e., splits)")

if splits:
    print("\nTop splits:")
    for txn_id, count in splits[:10]:
        print(f"  Transaction #{txn_id}: {count} receipts")
        
        # Get details of each receipt in this split
        cur.execute("""
            SELECT rbl.receipt_id, r.receipt_date, r.vendor_name, r.gross_amount,
                   rbl.linked_amount
            FROM receipt_banking_links rbl
            JOIN receipts r ON r.receipt_id = rbl.receipt_id
            WHERE rbl.transaction_id = %s
            ORDER BY r.receipt_id
        """, (txn_id,))
        
        for rid, date, vendor, amount, linked in cur.fetchall():
            print(f"    Receipt #{rid}: {date} | {vendor} | ${amount:,.2f} | Linked: ${linked:,.2f}")

# Show summary statistics
cur.execute("""
    SELECT 
        COUNT(DISTINCT rbl.transaction_id) as total_txns,
        COUNT(DISTINCT rbl.receipt_id) as total_receipts
    FROM receipt_banking_links rbl
""")

row = cur.fetchone()
print(f"\n📊 Summary:")
print(f"  Total banking transactions with links: {row[0]}")
print(f"  Total receipts with banking links: {row[1]}")

cur.close()
conn.close()

print("\n" + "="*80)
print("✅ TEST COMPLETE - Ready to load split receipts in UI")
print("="*80 + "\n")
