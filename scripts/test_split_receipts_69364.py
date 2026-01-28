#!/usr/bin/env python
"""
Test script: Create split receipts for banking transaction ID 69364
From the screenshot: Banking 69364, amount $170.01 (Centex)
Splits: Fuel $102.54 + Food $67.47 = $170.01

This simulates what the "Divide by Payment Methods" dialog will do
"""

import psycopg2
from datetime import datetime

# Connect to database
conn = psycopg2.connect(
    host='localhost',
    user='postgres',
    password='***REMOVED***',
    dbname='almsdata'
)
cur = conn.cursor()

try:
    # Get banking transaction details
    cur.execute("""
        SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE transaction_id = 69364
    """)
    
    banking = cur.fetchone()
    if not banking:
        print("❌ Banking transaction 69364 not found")
        exit(1)
    
    banking_id, bank_date, bank_desc, debit, credit = banking
    bank_amount = float(debit or credit or 0.0)
    
    print(f"✅ Found Banking Transaction 69364:")
    print(f"   Date: {bank_date}")
    print(f"   Description: {bank_desc}")
    print(f"   Amount: ${bank_amount:,.2f}\n")
    
    # Create parent receipt from banking
    print(f"📝 Creating split receipts for ${bank_amount:,.2f}...\n")
    
    # Split configuration (from screenshot or user input)
    splits = [
        {"amount": 102.54, "gl_code": "5110", "payment_method": "debit", "memo": "Fuel", "vendor_part": "CENTEX"},
        {"amount": 67.47, "gl_code": "5100", "payment_method": "debit", "memo": "Oil", "vendor_part": "CENTEX"}
    ]
    
    # Verify totals
    total = sum(s["amount"] for s in splits)
    print(f"Configuration:")
    for i, s in enumerate(splits, 1):
        print(f"  Split {i}: ${s['amount']:.2f} | GL {s['gl_code']} | {s['payment_method'].upper()} | {s['memo']}")
    print(f"  Total: ${total:,.2f}")
    
    if abs(total - bank_amount) > 0.01:
        print(f"❌ Split total {total:.2f} does NOT match banking {bank_amount:.2f}")
        exit(1)
    
    print(f"✅ Totals match!\n")
    
    # Generate split tag
    split_tag = f"SPLIT/{bank_amount:.2f}"
    print(f"Using SPLIT tag: {split_tag}\n")
    
    # Create split receipts
    new_receipt_ids = []
    
    for idx, split in enumerate(splits):
        amount = split["amount"]
        gl_code = split["gl_code"]
        payment_method = split["payment_method"]
        memo = split["memo"]
        
        # GST calculation (tax-inclusive 5% if code is GST_INCL_5)
        line_gst = amount * 0.05 / 1.05  # Assuming GST_INCL_5
        
        # Description with memo and split tag
        full_desc = f"Centex | {memo} | {split_tag}"
        
        # Only link first split to banking
        link_banking = banking_id if idx == 0 else None
        
        # Get GL name
        cur.execute("SELECT account_name FROM chart_of_accounts WHERE account_code = %s", (gl_code,))
        gl_result = cur.fetchone()
        gl_name = gl_result[0] if gl_result else gl_code
        
        # Insert receipt
        insert_sql = """
            INSERT INTO receipts (
                receipt_date, vendor_name, canonical_vendor, gross_amount,
                gst_amount, gst_code, sales_tax, tax_category,
                description, category, source_reference, payment_method,
                banking_transaction_id, is_driver_reimbursement, vehicle_id,
                gl_account_code, gl_account_name, owner_personal_amount, fuel_amount
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING receipt_id
        """
        
        params = (
            bank_date,           # receipt_date
            "Centex",            # vendor_name
            "Centex",            # canonical_vendor
            amount,              # gross_amount
            line_gst,            # gst_amount
            "GST_INCL_5",        # gst_code
            0.0,                 # sales_tax (PST)
            "Business",          # tax_category
            full_desc,           # description
            None,                # category
            None,                # source_reference
            payment_method,      # payment_method
            link_banking,        # banking_transaction_id
            False,               # is_driver_reimbursement
            None,                # vehicle_id
            gl_code,             # gl_account_code
            gl_name,             # gl_account_name
            0.0,                 # owner_personal_amount
            0.0                  # fuel_amount
        )
        
        cur.execute(insert_sql, params)
        new_receipt_id = cur.fetchone()[0]
        new_receipt_ids.append(new_receipt_id)
        
        print(f"✅ Created Receipt #{new_receipt_id}")
        print(f"   Amount: ${amount:.2f}")
        print(f"   GST: ${line_gst:.2f}")
        print(f"   GL: {gl_code} ({gl_name})")
        print(f"   Payment: {payment_method.upper()}")
        print(f"   Memo: {memo}")
        if link_banking:
            print(f"   Banking Link: YES (ID {banking_id})")
        else:
            print(f"   Banking Link: NO")
        print()
        
        # Create banking ledger entry for first split
        if link_banking:
            cur.execute("""
                INSERT INTO banking_receipt_matching_ledger (
                    banking_transaction_id, receipt_id, match_date, match_type,
                    match_status, match_confidence, notes, created_by
                )
                VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s)
            """, (
                link_banking,
                new_receipt_id,
                "split_first",
                "linked",
                0.95,
                f"First split of {split_tag}",
                "test_script"
            ))
            print(f"✅ Ledger entry created for Receipt #{new_receipt_id}")
    
    conn.commit()
    
    print("\n" + "="*60)
    print(f"✅ SUCCESS: Created {len(new_receipt_ids)} split receipts")
    print("="*60)
    print(f"\nReceipt IDs: {', '.join(str(rid) for rid in new_receipt_ids)}")
    print(f"Split tag: {split_tag}")
    print(f"Banking link: Receipt #{new_receipt_ids[0]} only")
    print(f"\nTo verify in database:")
    print(f"  SELECT receipt_id, gross_amount, description, payment_method, banking_transaction_id")
    print(f"  FROM receipts WHERE receipt_id IN ({', '.join(str(rid) for rid in new_receipt_ids)})")
    
except Exception as e:
    conn.rollback()
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

finally:
    cur.close()
    conn.close()
