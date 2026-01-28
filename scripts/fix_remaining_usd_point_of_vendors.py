#!/usr/bin/env python3
"""
Fix remaining 55 USD/INTL receipts that are still "POINT OF".
Extract vendor names and conversion rates from banking descriptions.
"""

import psycopg2
import re

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

def extract_vendor_and_rate(banking_desc):
    """Extract vendor name and conversion rate from banking description."""
    
    # Pattern: "INTL VISA DEB RETAIL PURCHASE <VENDOR> <TRANSACTION_ID> <USD_AMT> USD @ <RATE>"
    match = re.search(r'INTL VISA DEB RETAIL PURCHASE\s+([A-Z0-9\s\.\*\-]+?)\s+(\d{12,})\s+([\d\.]+)\s+USD\s+@\s+([\d\.]+)', banking_desc)
    
    if match:
        vendor = match.group(1).strip()
        transaction_id = match.group(2)
        usd_amount = match.group(3)
        rate = match.group(4)
        return vendor, usd_amount, rate
    
    # Alternative pattern for CAD transactions
    match = re.search(r'INTL VISA DEB RETAIL PURCHASE\s+([A-Z0-9\s\.\*\-]+?)\s+(\d{12,})\s+([\d\.]+)\s+CAD\s+@\s+([\d\.]+)', banking_desc)
    
    if match:
        vendor = match.group(1).strip()
        transaction_id = match.group(2)
        cad_amount = match.group(3)
        rate = match.group(4)
        return vendor, cad_amount, rate
    
    return None, None, None

def standardize_vendor_name(vendor):
    """Standardize vendor names."""
    vendor = vendor.strip()
    
    # Known vendors
    if 'WWW.1AND1.COM' in vendor or '1AND1' in vendor or '1&1' in vendor:
        return 'IONOS (1&1.COM) (USD)'
    elif 'WIX.COM' in vendor or 'WIX*' in vendor:
        return 'WIX.COM (USD)'
    elif 'INFINITE INNOVA' in vendor:
        return 'INFINITE INNOVATIONS (USD)'
    elif 'VCITA' in vendor:
        return 'VCITA INC (USD)'
    elif 'GOOGLE' in vendor or 'GSUITE' in vendor:
        return 'GOOGLE WORKSPACE'  # Not USD, CAD
    elif 'IONOS' in vendor:
        return 'IONOS WEBSITE HOSTING SERVICES (USD)'
    elif 'BEAVERHEAD' in vendor:
        return 'BEAVERHEAD INN (USD)'
    elif 'HTSP' in vendor:
        return 'HTSP'  # Not USD, CAD
    else:
        return f"{vendor} (USD)"

def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("FIXING REMAINING USD POINT OF VENDORS")
    print("=" * 80)
    
    # Get all POINT OF receipts with INTL in banking
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
        WHERE r.vendor_name = 'POINT OF'
          AND bt.description LIKE '%INTL VISA DEB RETAIL PURCHASE%'
        ORDER BY r.receipt_date
    """)
    
    point_of_intl = cur.fetchall()
    print(f"\nFound {len(point_of_intl)} POINT OF receipts with INTL transactions")
    
    updates = []
    failed = []
    
    for receipt_id, date, vendor, amount, desc, banking_desc in point_of_intl:
        vendor_name, usd_or_cad, rate = extract_vendor_and_rate(banking_desc)
        
        if vendor_name and rate:
            standardized = standardize_vendor_name(vendor_name)
            new_desc = f"${usd_or_cad} @ {rate}"
            
            updates.append((standardized, new_desc, receipt_id, vendor_name, usd_or_cad, rate))
            print(f"  {receipt_id} | {date} | {standardized[:40]:40} | ${usd_or_cad} @ {rate}")
        else:
            failed.append((receipt_id, date, amount, banking_desc))
            print(f"  ⚠️  {receipt_id} | {date} | ${amount:,.2f} | FAILED to extract")
    
    print(f"\n{len(updates)} successful extractions, {len(failed)} failed")
    
    if updates:
        print("\nApplying updates...")
        for standardized, new_desc, receipt_id, _, _, _ in updates:
            cur.execute("""
                UPDATE receipts
                SET vendor_name = %s,
                    description = %s
                WHERE receipt_id = %s
            """, (standardized, new_desc, receipt_id))
        
        conn.commit()
        print(f"✅ Updated {len(updates)} POINT OF receipts with vendor names and conversion rates")
    
    if failed:
        print(f"\n⚠️  {len(failed)} receipts failed extraction:")
        for receipt_id, date, amount, banking_desc in failed:
            print(f"  {receipt_id} | {date} | ${amount:,.2f}")
            print(f"    Banking: {banking_desc[:100]}")
    
    # Verify completion
    cur.execute("""
        SELECT COUNT(*)
        FROM receipts r
        JOIN banking_receipt_matching_ledger brml ON r.receipt_id = brml.receipt_id
        JOIN banking_transactions bt ON brml.banking_transaction_id = bt.transaction_id
        WHERE (bt.description LIKE '%INTL%' OR r.vendor_name LIKE '%(USD)%')
          AND (r.description IS NULL OR (r.description NOT LIKE '%@%' AND r.description NOT LIKE '%USD%'))
          AND r.vendor_name NOT LIKE '%GOOGLE%'
          AND r.vendor_name NOT LIKE '%HTSP%'
    """)
    
    remaining = cur.fetchone()[0]
    print(f"\n{remaining} receipts still missing conversion tracking (excluding CAD transactions)")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
