#!/usr/bin/env python3
"""Check WCB BANKING_IMPORT invoice issues."""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

cur = conn.cursor()

# First check what tables exist
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name LIKE '%vendor%'
""")
print("Vendor-related tables:")
for row in cur.fetchall():
    print(f"  - {row[0]}")

# Check if receipts table has WCB from banking
cur.execute("""
    SELECT COUNT(*) 
    FROM receipts 
    WHERE vendor_name = 'WCB' 
    AND created_from_banking = TRUE
""")
count = cur.fetchone()[0]
print(f"\nFound {count} WCB receipts created from banking\n")

# Check WCB receipts that came from banking
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.vendor_name,
        r.description,
        r.gross_amount,
        r.created_from_banking,
        r.banking_transaction_id,
        bt.description as bank_desc,
        bt.debit_amount,
        bt.credit_amount,
        bt.category as bank_category
    FROM receipts r
    LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name = 'WCB' 
    AND r.created_from_banking = TRUE
    ORDER BY r.receipt_date
""")

rows = cur.fetchall()

print(f"Found {len(rows)} WCB receipts from banking:\n")
print(f"{'Receipt ID':<10} {'Date':<12} {'Description':<30} {'Amount':<12} {'Bank ID':<8} {'Debit':<12} {'Credit':<12} {'Category':<20}")
print("-" * 150)

for r in rows:
    receipt_id, date, vendor, desc, amt, from_banking, bank_id, bank_desc, debit, credit, category = r
    desc_short = (desc[:28] if desc else "N/A")
    bank_id_str = str(bank_id) if bank_id else "N/A"
    debit_str = f"${debit:,.2f}" if debit else "$0.00"
    credit_str = f"${credit:,.2f}" if credit else "$0.00"
    category_str = (category[:18] if category else "N/A")
    
    print(f"{receipt_id:<10} {date} {desc_short:<30} ${amt:>10,.2f} {bank_id_str:<8} {debit_str:<12} {credit_str:<12} {category_str:<20}")

# Check if these banking transactions are actually WITHDRAWALS (payments out)
print("\n\nChecking banking transaction details for these WCB transactions:")
cur.execute("""
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        bt.description,
        bt.debit_amount,
        bt.credit_amount,
        bt.category,
        bt.vendor_extracted
    FROM banking_transactions bt
    WHERE bt.transaction_id IN (
        SELECT banking_transaction_id 
        FROM receipts 
        WHERE vendor_name = 'WCB' 
        AND banking_transaction_id IS NOT NULL
    )
    ORDER BY bt.transaction_date
""")

bank_rows = cur.fetchall()
print(f"\n{'Bank ID':<10} {'Date':<12} {'Debit':<12} {'Credit':<12} {'Category':<20} {'Vendor':<15} {'Description'[:40]}")
print("-" * 140)
for r in bank_rows:
    tid, date, desc, debit, credit, category, vendor = r
    debit_str = f"${debit:,.2f}" if debit else "$0.00"
    credit_str = f"${credit:,.2f}" if credit else "$0.00"
    category_str = (category[:18] if category else "N/A")
    vendor_str = (vendor[:13] if vendor else "N/A")
    print(f"{tid:<10} {date} {debit_str:<12} {credit_str:<12} {category_str:<20} {vendor_str:<15} {desc[:40] if desc else 'N/A'}")

cur.close()
conn.close()
