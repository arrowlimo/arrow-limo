#!/usr/bin/env python3
"""
Fix WCB BANKING_IMPORT invoices that show as unpaid.

Problem: Receipts created from banking transactions (already paid) are showing 
as unpaid invoices in the Vendor Invoice Manager because there are no corresponding
ledger entries marking them as paid.

Solution: Create vendor_account_ledger entries for these receipts to mark them as paid.
"""

import psycopg2
import os
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

cur = conn.cursor()

# Get WCB vendor account ID
cur.execute("""
    SELECT account_id FROM vendor_accounts WHERE canonical_vendor = 'WCB'
""")
result = cur.fetchone()

if not result:
    print("❌ WCB vendor account not found. Creating it...")
    cur.execute("""
        INSERT INTO vendor_accounts (canonical_vendor, display_name, status)
        VALUES ('WCB', 'WCB', 'active')
        RETURNING account_id
    """)
    vendor_account_id = cur.fetchone()[0]
    conn.commit()
    print(f"✅ Created WCB vendor account: {vendor_account_id}")
else:
    vendor_account_id = result[0]
    print(f"✅ Found WCB vendor account: {vendor_account_id}")

# Get all WCB receipts created from banking that don't have payment ledger entries
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.description,
        r.gross_amount,
        r.banking_transaction_id
    FROM receipts r
    WHERE r.vendor_name = 'WCB'
    AND r.created_from_banking = TRUE
    AND NOT EXISTS (
        SELECT 1 FROM vendor_account_ledger val
        WHERE val.account_id = %s
        AND val.source_id = CAST(r.receipt_id AS TEXT)
        AND val.entry_type = 'PAYMENT'
    )
    ORDER BY r.receipt_date
""", (vendor_account_id,))

wcb_receipts = cur.fetchall()

print(f"\nFound {len(wcb_receipts)} WCB receipts from banking without payment ledger entries:\n")

if len(wcb_receipts) == 0:
    print("✅ No WCB receipts need fixing. All are already marked as paid.")
    cur.close()
    conn.close()
    exit(0)

print(f"{'Receipt ID':<12} {'Date':<12} {'Amount':<12} {'Bank ID':<10} {'Description'[:30]}")
print("-" * 100)

for r in wcb_receipts:
    receipt_id, date, desc, amount, bank_id = r
    desc_short = (desc[:28] if desc else "N/A")
    bank_id_str = str(bank_id) if bank_id else "N/A"
    print(f"{receipt_id:<12} {date} ${amount:>10,.2f} {bank_id_str:<10} {desc_short}")

print("\n" + "="*100)
print("PROPOSED FIX:")
print("="*100)
print(f"Create vendor_account_ledger entries for these {len(wcb_receipts)} receipts")
print(f"to mark them as PAID (since they were created from actual bank debits).\n")

# Ask for confirmation
response = input("Create payment ledger entries? (yes/no): ").strip().lower()

if response != 'yes':
    print("❌ Aborted. No changes made.")
    cur.close()
    conn.close()
    exit(0)

# Create ledger entries
created_count = 0
for r in wcb_receipts:
    receipt_id, date, desc, amount, bank_id = r
    
    # Create a PAYMENT entry (negative amount to offset the invoice)
    payment_amount = -float(amount)  # Negative because it's a payment
    
    cur.execute("""
        INSERT INTO vendor_account_ledger (
            account_id,
            entry_date,
            entry_type,
            amount,
            notes,
            source_table,
            source_id,
            external_ref
        ) VALUES (%s, %s, 'PAYMENT', %s, %s, %s, %s, %s)
    """, (
        vendor_account_id,
        date,
        payment_amount,
        f"Payment via banking import (bank_id: {bank_id}) - {desc if desc else 'WCB'}",
        'receipts',
        str(receipt_id),
        f"BANKING_{bank_id}" if bank_id else None
    ))
    created_count += 1
    created_count += 1

conn.commit()

print(f"\n✅ Successfully created {created_count} payment ledger entries.")
print(f"✅ WCB receipts from banking are now marked as PAID.\n")

# Verify the fix
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.gross_amount,
        COALESCE(SUM(val.amount), 0) as total_ledger_amount,
        r.gross_amount + COALESCE(SUM(val.amount), 0) as balance
    FROM receipts r
    LEFT JOIN vendor_account_ledger val ON 
        val.account_id = %s AND 
        val.source_id = CAST(r.receipt_id AS TEXT)
    WHERE r.vendor_name = 'WCB'
    AND r.created_from_banking = TRUE
    GROUP BY r.receipt_id, r.receipt_date, r.gross_amount
    ORDER BY r.receipt_date
""", (vendor_account_id,))

verification = cur.fetchall()

print("\nVERIFICATION - WCB Receipts Balance After Fix:")
print(f"{'Receipt ID':<12} {'Date':<12} {'Amount':<12} {'Ledger':<12} {'Balance':<12} {'Status'}")
print("-" * 90)

all_zero = True
for r in verification:
    receipt_id, date, amount, ledger, balance = r
    amount_f = float(amount) if amount else 0.0
    ledger_f = float(ledger) if ledger else 0.0
    balance_f = float(balance) if balance else 0.0
    
    status = "✅ PAID" if abs(balance_f) < 0.01 else f"❌ {balance_f:+.2f} DUE"
    if abs(balance_f) >= 0.01:
        all_zero = False
    
    print(f"{receipt_id:<12} {date} ${amount_f:>10,.2f} ${ledger_f:>10,.2f} ${balance_f:>10,.2f} {status}")

if all_zero:
    print("\n✅✅✅ SUCCESS! All WCB receipts now show $0.00 balance (fully paid).")
else:
    print("\n⚠️  Warning: Some receipts still have non-zero balance. Manual review needed.")

cur.close()
conn.close()
