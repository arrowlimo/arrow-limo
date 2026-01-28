#!/usr/bin/env python3
"""
Fix the banking transactions that weren't found by matching on amount and date.
"""
import psycopg2
import os
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

try:
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("FIXING BANKING TRANSACTIONS")
    print("="*80)
    
    # The 3 banking transactions that need updating:
    # 1. 2012-12-30, payment, $686.65 (for invoice 18254512)
    # 2. 2012-08-28, PAYMENT, $3446.02 (for invoice 18604318) - TX 69282
    # 3. 2012-11-26, PAYMENT, $553.17 (for invoice 18714897) - TX 69587
    
    updates = [
        {
            'date': '2012-08-28',
            'amount': 3446.02,
            'description': 'WCB payment',
            'expected_tx_id': 69282
        },
        {
            'date': '2012-11-26',
            'amount': 553.17,
            'description': 'wcb payment',
            'expected_tx_id': 69587
        }
    ]
    
    for update in updates:
        print(f"\nUpdating: {update['date']} | ${update['amount']:.2f}")
        
        # Find by amount and date
        cur.execute("""
            SELECT transaction_id, transaction_date, debit_amount, description
            FROM banking_transactions
            WHERE ABS(debit_amount - %s) < 0.01
              AND transaction_date = %s
        """, (update['amount'], update['date']))
        
        result = cur.fetchone()
        if result:
            tx_id, tx_date, tx_amount, old_desc = result
            print(f"  Found TX {tx_id}: {tx_date} | ${float(tx_amount):.2f}")
            
            # Update description
            cur.execute("""
                UPDATE banking_transactions
                SET description = %s
                WHERE transaction_id = %s
            """, (update['description'], tx_id))
            
            print(f"  ✓ Updated description to: {update['description']}")
        else:
            print(f"  ✗ No transaction found for {update['date']} / ${update['amount']:.2f}")
    
    conn.commit()
    
    # Verify the refunded entry
    print(f"\n" + "-"*80)
    print("Checking refunded entry (wcb waived late filing penalty)...")
    
    # The refund on 2012-11-27 for $593.81 should be linked to receipt 145305
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount
        FROM receipts
        WHERE source_reference = '18604318'
          AND gross_amount = 593.81
    """)
    
    result = cur.fetchone()
    if result:
        receipt_id, rec_date, vendor, amount = result
        print(f"\nFound receipt {receipt_id}: {rec_date} | {vendor} | ${float(amount):.2f}")
        
        # Update the receipt with refund date
        cur.execute("""
            UPDATE receipts
            SET receipt_date = %s,
                description = %s
            WHERE receipt_id = %s
        """, ('2012-11-27', 'wcb waived late filing penalty', receipt_id))
        
        conn.commit()
        print(f"✓ Updated receipt date and description")
    else:
        print("Could not find the waived fee receipt")
    
    cur.close()
    conn.close()
    
    print(f"\n" + "="*80)
    print("COMPLETE")
    print("="*80)
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
