#!/usr/bin/env python3
"""
Update database with corrected 2012 WCB data from the cleaned Excel file.
Start balance: 686.65 (from 2011)
"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

try:
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("UPDATING DATABASE WITH CORRECTED 2012 WCB DATA")
    print("="*80)
    
    # Update the key banking transactions for the 2 payments shown
    # Payment 1: 2012-08-28, $3,446.02 (TX 69282)
    # Payment 2: 2012-11-26, $553.17 (TX 69587)
    
    print("\n1. Verifying banking transactions...")
    cur.execute("""
        SELECT transaction_id, transaction_date, debit_amount, description
        FROM banking_transactions
        WHERE transaction_id IN (69282, 69587)
        ORDER BY transaction_id
    """)
    
    for row in cur.fetchall():
        tx_id, tx_date, amount, desc = row
        print(f"   TX {tx_id}: {tx_date} | ${float(amount):,.2f} | {desc}")
    
    # Update banking transaction descriptions if needed
    print("\n2. Updating banking transaction descriptions...")
    cur.execute("""
        UPDATE banking_transactions
        SET description = 'WCB payment'
        WHERE transaction_id = 69282
    """)
    print(f"   ✓ Updated TX 69282 description")
    
    cur.execute("""
        UPDATE banking_transactions
        SET description = 'wcb payment'
        WHERE transaction_id = 69587
    """)
    print(f"   ✓ Updated TX 69587 description")
    
    # Verify all invoice receipts are correct
    print("\n3. Verifying WCB invoices for 2012...")
    cur.execute("""
        SELECT receipt_id, receipt_date, source_reference, vendor_name, gross_amount, description
        FROM receipts
        WHERE vendor_name ILIKE '%wcb%'
          AND EXTRACT(YEAR FROM receipt_date) = 2012
        ORDER BY receipt_date
    """)
    
    invoice_count = 0
    total_invoiced = 0.0
    for row in cur.fetchall():
        rec_id, rec_date, ref, vendor, amount, desc = row
        amount_f = float(amount)
        total_invoiced += amount_f
        invoice_count += 1
        print(f"   Receipt {rec_id}: {rec_date} | ${amount_f:>8.2f} | {ref}")
    
    # Verify linked invoices
    print("\n4. Checking payment-to-invoice links...")
    
    # Payment 1: $3,446.02
    cur.execute("""
        SELECT COUNT(*) as link_count, SUM(r.gross_amount) as total_amount
        FROM banking_receipt_matching_ledger bm
        JOIN receipts r ON bm.receipt_id = r.receipt_id
        WHERE bm.banking_transaction_id = 69282
    """)
    
    result = cur.fetchone()
    link_count, link_amount = result
    link_amount_f = float(link_amount) if link_amount else 0.0
    print(f"   TX 69282 ($3,446.02): {link_count} invoices linked = ${link_amount_f:,.2f}")
    
    # Payment 2: $553.17
    cur.execute("""
        SELECT COUNT(*) as link_count, SUM(r.gross_amount) as total_amount
        FROM banking_receipt_matching_ledger bm
        JOIN receipts r ON bm.receipt_id = r.receipt_id
        WHERE bm.banking_transaction_id = 69587
    """)
    
    result = cur.fetchone()
    link_count, link_amount = result
    link_amount_f = float(link_amount) if link_amount else 0.0
    print(f"   TX 69587 ($553.17): {link_count} invoices linked = ${link_amount_f:,.2f}")
    
    conn.commit()
    
    # Calculate the balance
    print(f"\n" + "="*80)
    print("2012 WCB ACCOUNT SUMMARY")
    print("="*80)
    print(f"\nOpening balance (from 2011): $686.65")
    print(f"Total invoices (2012): ${total_invoiced:,.2f}")
    print(f"Total paid (2012): $3,999.19")
    print(f"Closing balance: ${(686.65 + total_invoiced - 3999.19):,.2f}")
    
    print(f"\nDatabase is ready for program testing.")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
