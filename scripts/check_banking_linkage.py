#!/usr/bin/env python3
"""Check banking linkage status for Wix and IONOS receipts"""
import os, psycopg2

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***'),
)
cur = conn.cursor()

print("\n=== BANKING LINKAGE STATUS ===\n")

# Check receipts with banking links
cur.execute("""
    SELECT COUNT(DISTINCT r.receipt_id), SUM(r.gross_amount)
    FROM banking_receipt_matching_ledger bm 
    JOIN receipts r ON bm.receipt_id = r.receipt_id 
    WHERE r.vendor_name ILIKE 'wix%' OR r.vendor_name ILIKE 'ionos%'
""")
linked_count, linked_amt = cur.fetchone()
print(f"Receipts WITH banking links: {linked_count or 0} receipts, ${linked_amt or 0:,.2f}")

# Check banking transactions for Wix/IONOS
cur.execute("""
    SELECT COUNT(*), SUM(debit_amount) 
    FROM banking_transactions 
    WHERE (description ILIKE '%wix%' OR description ILIKE '%ionos%') 
    AND debit_amount > 0
""")
banking_count, banking_amt = cur.fetchone()
print(f"Banking debits found: {banking_count or 0} transactions, ${banking_amt or 0:,.2f}")

# Check if banking transactions have USD/FX data
cur.execute("""
    SELECT 
        description,
        debit_amount,
        transaction_date
    FROM banking_transactions 
    WHERE (description ILIKE '%wix%' OR description ILIKE '%ionos%') 
    AND debit_amount > 0
    AND description ILIKE '%USD%'
    ORDER BY transaction_date DESC
    LIMIT 5
""")
print(f"\nSample banking with USD/FX data:")
for desc, amt, date in cur.fetchall():
    print(f"  {date}: ${amt:>8.2f} - {desc[:60]}")

conn.close()
