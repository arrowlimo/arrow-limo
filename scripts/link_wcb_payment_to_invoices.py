#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Link WCB banking payment (ID 69282, $3,446.02) to invoice 18604318 line items
"""

import psycopg2
from decimal import Decimal

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)

print("=" * 80)
print("LINKING WCB PAYMENT TO INVOICE 18604318")
print("=" * 80)

cur = conn.cursor()

# Step 1: Verify the banking transaction
print("\n1. Verifying banking transaction 69282...")
cur.execute("""
    SELECT transaction_id, transaction_date, debit_amount, description
    FROM banking_transactions
    WHERE transaction_id = 69282
""")
row = cur.fetchone()
if row:
    print(f"   ✓ Found: ID {row[0]}, Date {row[1]}, Amount ${row[2]:.2f}, Desc: {row[3]}")
    banking_amount = float(row[2])  # Convert to float
else:
    print("   ✗ Banking transaction 69282 not found!")
    cur.close()
    conn.close()
    exit(1)

# Step 2: Get the 4 receipt line items for invoice 18604318
print("\n2. Finding invoice 18604318 line items...")
cur.execute("""
    SELECT receipt_id, receipt_date, gross_amount, description
    FROM receipts
    WHERE source_reference LIKE '%18604318%'
    AND gross_amount IN (26.91, 42.59, 470.85, 593.81)
    ORDER BY receipt_date, gross_amount
""")
receipts = cur.fetchall()

if len(receipts) == 0:
    print("   ✗ No receipts found! Checking with different query...")
    # Try alternative search
    cur.execute("""
        SELECT receipt_id, receipt_date, gross_amount, description
        FROM receipts  
        WHERE receipt_id IN (145302, 145304, 145305, 145309)
        ORDER BY receipt_date, gross_amount
    """)
    receipts = cur.fetchall()

print(f"   Found {len(receipts)} receipt line items:")
total_invoiced = Decimal('0.00')
receipt_list = []
for r in receipts:
    amount_f = float(r[2])
    print(f"     Receipt {r[0]}: ${amount_f:.2f} ({r[1]})")
    total_invoiced += Decimal(str(r[2]))
    receipt_list.append((r[0], r[1], amount_f, r[3]))

print(f"   Total invoice amount: ${float(total_invoiced):.2f}")
print(f"   Payment amount: ${banking_amount:.2f}")
print(f"   Remaining after these items: ${banking_amount - float(total_invoiced):.2f}")

# Step 3: Check if there's a banking_receipt_matching_ledger table
print("\n3. Checking for existing links...")
cur.execute("""
    SELECT table_name FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name IN ('banking_receipt_matching_ledger', 'banking_payment_links', 'invoice_payments')
""")
link_tables = [r[0] for r in cur.fetchall()]
print(f"   Available link tables: {', '.join(link_tables) if link_tables else 'None found'}")

# Step 4: Create the links using banking_receipt_matching_ledger
print("\n4. Creating payment allocation links...")
print("\nLinking receipts to banking transaction 69282 via banking_receipt_matching_ledger...")

for receipt_id, receipt_date, amount_f, desc in receipt_list:
    try:
        # Update receipt with banking_transaction_id
        cur.execute("""
            UPDATE receipts
            SET banking_transaction_id = %s
            WHERE receipt_id = %s
        """, (69282, receipt_id))
        
        # Create ledger entry
        cur.execute("""
            INSERT INTO banking_receipt_matching_ledger (
                banking_transaction_id, receipt_id, match_date, match_type, 
                match_status, match_confidence, notes, created_by
            ) VALUES (
                %s, %s, NOW(), %s, %s, %s, %s, %s
            )
        """, (
            69282,
            receipt_id,
            "allocation",
            "linked",
            "exact" if abs(amount_f - banking_amount) < 0.01 else "partial",
            f"WCB invoice 18604318 component; ${amount_f:.2f}",
            "SYSTEM_RECOVERY"
        ))
        
        print(f"   ✓ Linked Receipt {receipt_id}: ${amount_f:.2f}")
    except Exception as e:
        print(f"   ✗ Failed to link Receipt {receipt_id}: {e}")
        conn.rollback()
        cur.close()
        conn.close()
        exit(1)

conn.commit()
cur.close()
conn.close()

print("\n" + "=" * 80)
print("SUCCESS - Links created")
print("=" * 80)
print(f"\nLinked {len(receipt_list)} invoices to payment TX 69282")
print(f"Total invoice amount: ${float(total_invoiced):.2f}")
print(f"Payment amount: ${banking_amount:.2f}")
print(f"Variance: ${banking_amount - float(total_invoiced):.2f}")
print("\nThe invoices are now linked to the payment in the database.")
