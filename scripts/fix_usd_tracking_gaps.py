#!/usr/bin/env python3
"""
Fix USD tracking gaps for audit compliance.

Issues to fix:
1. Mark 20 LMS INTL transactions as "LMS (USD)" 
2. Extract conversion rates from banking descriptions
3. Add conversion rate to AMERICAN FUNDS CASH WITHDRAWAL
"""

import psycopg2
import re
from datetime import datetime

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("USD TRACKING GAP FIXES")
    print("=" * 80)
    
    # Fix 1: Mark LMS INTL transactions as USD and extract conversion rates
    print("\n1. Fixing LMS INTL transactions (20 expected)...")
    cur.execute("""
        SELECT 
            r.receipt_id,
            r.vendor_name,
            r.gross_amount,
            r.description,
            bt.transaction_id,
            bt.description as banking_desc
        FROM receipts r
        JOIN banking_receipt_matching_ledger brml ON r.receipt_id = brml.receipt_id
        JOIN banking_transactions bt ON brml.banking_transaction_id = bt.transaction_id
        WHERE r.vendor_name = 'LMS'
          AND bt.description LIKE '%INTL VISA DEB RETAIL PURCHASE%'
          AND r.vendor_name NOT LIKE '%(USD)%'
        ORDER BY r.receipt_date, r.gross_amount DESC
    """)
    
    lms_intl = cur.fetchall()
    print(f"Found {len(lms_intl)} LMS INTL transactions to fix")
    
    lms_updates = []
    for receipt_id, vendor, amount, desc, tx_id, banking_desc in lms_intl:
        # Extract conversion rate from banking description
        # Format: "XXX.XX USD @ 1.XXXX" or similar
        conversion_match = re.search(r'(\d+\.\d+)\s*USD\s*@\s*(1\.\d+)', banking_desc)
        
        new_vendor = "LMS (USD)"
        new_desc = desc or ""
        
        if conversion_match:
            usd_amount = conversion_match.group(1)
            rate = conversion_match.group(2)
            if not new_desc:
                new_desc = f"${usd_amount} USD @ {rate}"
            elif "@" not in new_desc:
                new_desc += f" @ {rate}"
            conversion_info = f"${usd_amount} USD @ {rate}"
        else:
            conversion_info = "No rate found"
        
        lms_updates.append((new_vendor, new_desc, receipt_id, amount, conversion_info))
        print(f"  Receipt {receipt_id}: ${amount:,.2f} CAD = {conversion_info}")
    
    if lms_updates:
        print(f"\nApplying {len(lms_updates)} LMS updates...")
        for new_vendor, new_desc, receipt_id, amount, _ in lms_updates:
            cur.execute("""
                UPDATE receipts 
                SET vendor_name = %s,
                    description = %s
                WHERE receipt_id = %s
            """, (new_vendor, new_desc, receipt_id))
        print(f"✅ Updated {len(lms_updates)} LMS receipts to 'LMS (USD)' with conversion rates")
    
    # Fix 2: AMERICAN FUNDS CASH WITHDRAWAL - extract conversion from banking
    print("\n2. Fixing AMERICAN FUNDS CASH WITHDRAWAL conversion rate...")
    cur.execute("""
        SELECT 
            r.receipt_id,
            r.vendor_name,
            r.gross_amount,
            r.description,
            bt.transaction_id,
            bt.description as banking_desc
        FROM receipts r
        JOIN banking_receipt_matching_ledger brml ON r.receipt_id = brml.receipt_id
        JOIN banking_transactions bt ON brml.banking_transaction_id = bt.transaction_id
        WHERE r.vendor_name LIKE 'AMERICAN FUNDS%'
          AND bt.description LIKE '%INTL ABM WD%'
          AND (r.description IS NULL OR r.description NOT LIKE '%@%')
    """)
    
    american_funds = cur.fetchall()
    print(f"Found {len(american_funds)} AMERICAN FUNDS transactions to fix")
    
    af_updates = []
    for receipt_id, vendor, amount, desc, tx_id, banking_desc in american_funds:
        # Extract from format: "INTL ABM WD * 9000 470.29 CAD X 1.000000"
        # Look for "X 1.XXXX" pattern
        conversion_match = re.search(r'(\d+\.\d+)\s*CAD\s*X\s*(1\.\d+)', banking_desc)
        
        new_desc = desc or ""
        
        if conversion_match:
            cad_amount = conversion_match.group(1)
            rate = conversion_match.group(2)
            conversion_info = f"@ {rate}"
            if not new_desc:
                new_desc = conversion_info
            elif "@" not in new_desc:
                new_desc += f" {conversion_info}"
            print(f"  Receipt {receipt_id}: ${amount:,.2f} CAD X {rate}")
        else:
            conversion_info = "No rate found"
            print(f"  Receipt {receipt_id}: ${amount:,.2f} - {conversion_info}")
        
        af_updates.append((new_desc, receipt_id))
    
    if af_updates:
        print(f"\nApplying {len(af_updates)} AMERICAN FUNDS updates...")
        for new_desc, receipt_id in af_updates:
            cur.execute("""
                UPDATE receipts 
                SET description = %s
                WHERE receipt_id = %s
            """, (new_desc, receipt_id))
        print(f"✅ Updated {len(af_updates)} AMERICAN FUNDS receipts with conversion rates")
    
    # Verify all USD/INTL tracking is complete
    print("\n3. Verifying USD tracking completeness...")
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN r.description LIKE '%@%' OR r.description LIKE '%USD%' THEN 1 END) as with_tracking
        FROM receipts r
        JOIN banking_receipt_matching_ledger brml ON r.receipt_id = brml.receipt_id
        JOIN banking_transactions bt ON brml.banking_transaction_id = bt.transaction_id
        WHERE bt.description LIKE '%INTL%'
           OR r.vendor_name LIKE '%(USD)%'
           OR r.description LIKE '%USD%'
    """)
    
    total, with_tracking = cur.fetchone()
    print(f"Total USD/INTL receipts: {total}")
    print(f"With conversion tracking: {with_tracking}")
    print(f"Missing tracking: {total - with_tracking}")
    
    if total - with_tracking == 0:
        print("✅ All USD/INTL purchases have conversion tracking!")
    else:
        print("\n⚠️  Still missing conversion tracking:")
        cur.execute("""
            SELECT 
                r.receipt_id,
                r.receipt_date,
                r.vendor_name,
                r.gross_amount,
                r.description,
                bt.description as banking_desc
            FROM receipts r
            JOIN banking_receipt_matching_ledger brml ON r.receipt_id = brml.receipt_id
            JOIN banking_transactions bt ON brml.banking_transaction_id = bt.transaction_id
            WHERE (bt.description LIKE '%INTL%'
               OR r.vendor_name LIKE '%(USD)%'
               OR r.description LIKE '%USD%')
              AND (r.description IS NULL 
               OR (r.description NOT LIKE '%@%' AND r.description NOT LIKE '%USD%'))
            ORDER BY r.receipt_date, r.gross_amount DESC
        """)
        
        missing = cur.fetchall()
        for receipt_id, date, vendor, amount, desc, banking_desc in missing:
            print(f"  Receipt {receipt_id} ({date}): {vendor} ${amount:,.2f}")
            print(f"    Description: {desc}")
            print(f"    Banking: {banking_desc[:100]}")
    
    # Commit changes
    conn.commit()
    print(f"\n✅ All USD tracking fixes committed to database")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
