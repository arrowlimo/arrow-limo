#!/usr/bin/env python3
import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

print("="*70)
print("WCB INVOICE SUMMARY")
print("="*70)

# Show sample WCB invoices
cur.execute("""
    SELECT receipt_id, source_reference, receipt_date, gross_amount, vendor_name
    FROM receipts
    WHERE vendor_name = 'WCB'
    ORDER BY receipt_date
    LIMIT 25
""")

for row in cur.fetchall():
    print(f"ID {row[0]:6} | Ref {row[1]:12} | Date {row[2]} | Amount ${row[3]:10,.2f} | {row[4]}")

print(f"\n{'='*70}")
print("LINKED PAYMENTS CHECK")
print("="*70)

# Check banking transactions
cur.execute("""
    SELECT bt.transaction_id, bt.description, bt.credit_amount, 
           COUNT(brml.receipt_id) as linked_invoices
    FROM banking_transactions bt
    LEFT JOIN banking_receipt_matching_ledger brml ON brml.banking_transaction_id = bt.transaction_id
    WHERE bt.description LIKE '%WCB%' OR bt.transaction_id IN (69282, 69587)
    GROUP BY bt.transaction_id, bt.description, bt.credit_amount
    ORDER BY bt.transaction_id
""")

for row in cur.fetchall():
    print(f"TX {row[0]:6} | {row[1]:30} | ${row[2]:10,.2f} | {row[3]} linked")

print(f"\n{'='*70}")
print("CHECK: Do invoices have banking_transaction_id set?")
print("="*70)

cur.execute("""
    SELECT COUNT(*) as total_wcb_invoices,
           COUNT(CASE WHEN banking_transaction_id IS NOT NULL THEN 1 END) as with_banking_link,
           COUNT(CASE WHEN banking_transaction_id IS NULL THEN 1 END) as without_banking_link
    FROM receipts
    WHERE vendor_name = 'WCB'
""")

total, with_link, without_link = cur.fetchone()
print(f"Total WCB Invoices: {total}")
print(f"  With banking_transaction_id: {with_link}")
print(f"  Without banking_transaction_id: {without_link}")

conn.close()
