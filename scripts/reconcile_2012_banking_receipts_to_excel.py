#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
2012 Banking-Receipts Reconciliation and Excel Export
Creates receipts for unmatched banking debits, then exports to Excel for manual review.
"""

import psycopg2
import pandas as pd
import hashlib
from datetime import datetime

def generate_hash(date, description, amount):
    """Generate deterministic hash for transaction."""
    hash_input = f"{date}|{description}|{amount:.2f}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def calculate_gst(gross_amount, tax_rate=0.05):
    """Calculate GST included in amount (Alberta 5% GST)."""
    gst_amount = gross_amount * tax_rate / (1 + tax_rate)
    net_amount = gross_amount - gst_amount
    return round(gst_amount, 2), round(net_amount, 2)

def extract_vendor_from_description(description):
    """Extract vendor name from banking description."""
    if not description:
        return "Unknown Vendor"
    
    # Remove common prefixes
    desc = description.upper()
    prefixes = ['PURCHASE', 'DEBIT MEMO', 'PRE-AUTH', 'CHEQUE', 'CHQ', 'TRANSFER', 'WITHDRAWAL', 'ABM']
    for prefix in prefixes:
        if desc.startswith(prefix):
            desc = desc[len(prefix):].strip()
    
    # Remove card numbers
    import re
    desc = re.sub(r'\d{4}\*+\d{3,4}', '', desc)
    
    # Clean up
    desc = desc.strip()
    return desc[:100] if desc else "Unknown Vendor"

def categorize_transaction(description):
    """Categorize transaction into expense category."""
    if not description:
        return 'uncategorized'
    
    desc = description.upper()
    
    categories = {
        'fuel': ['CENTEX', 'FAS GAS', 'SHELL', 'ESSO', 'PETRO', 'HUSKY', 'CO-OP', 'GAS', 'PETROLEUM'],
        'office_supplies': ['STAPLES', 'OFFICE DEPOT'],
        'maintenance': ['CANADIAN TIRE', 'MIDAS', 'JIFFY', 'REPAIR'],
        'communication': ['TELUS', 'ROGERS', 'BELL', 'SASKTEL'],
        'bank_fees': ['FEE', 'NSF', 'OVERDRAFT', 'SERVICE CHARGE', 'S/C'],
        'insurance': ['INSURANCE', 'SGI', 'AVIVA', 'JEVCO'],
        'equipment_lease': ['HEFFNER', 'LEASE', 'FINANCING'],
        'government_fees': ['CRA', 'CANADA REVENUE', 'WCB', 'RECEIVER GENERAL'],
        'credit_card_payment': ['MCC PAYMENT', 'CREDIT CARD', 'AMEX', 'VISA', 'MASTERCARD'],
        'rent': ['RENT', 'LANDLORD', 'FIBRENEW'],
        'hospitality_supplies': ['LIQUOR', 'BAR', 'PUB', 'BEVERAGE'],
        'meals_entertainment': ['RESTAURANT', 'FOOD', 'TIM HORTONS', 'MCDONALDS', 'A&W'],
        'cheque_payment': ['CHEQUE', 'CHQ'],
        'transfer': ['TRANSFER', 'WITHDRAWAL'],
    }
    
    for category, keywords in categories.items():
        if any(keyword in desc for keyword in keywords):
            return category
    
    return 'uncategorized'

def main():
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    cur = conn.cursor()
    
    print("=" * 100)
    print("2012 BANKING-RECEIPTS RECONCILIATION")
    print("=" * 100)
    
    # Get all 2012 banking debits
    cur.execute("""
        SELECT 
            bt.transaction_id,
            bt.account_number,
            bt.transaction_date,
            bt.description,
            bt.debit_amount,
            CASE 
                WHEN EXISTS (
                    SELECT 1 FROM banking_receipt_matching_ledger bm 
                    WHERE bm.banking_transaction_id = bt.transaction_id
                ) THEN 'Matched'
                ELSE 'Unmatched'
            END as match_status
        FROM banking_transactions bt
        WHERE EXTRACT(YEAR FROM bt.transaction_date) = 2012
        AND bt.debit_amount > 0
        ORDER BY bt.account_number, bt.transaction_date
    """)
    
    all_debits = cur.fetchall()
    total_debits = len(all_debits)
    matched_count = sum(1 for row in all_debits if row[5] == 'Matched')
    unmatched_count = total_debits - matched_count
    
    print(f"\n2012 Banking Debits Summary:")
    print(f"  Total Debits: {total_debits}")
    print(f"  Matched: {matched_count} ({matched_count/total_debits*100:.1f}%)")
    print(f"  Unmatched: {unmatched_count} ({unmatched_count/total_debits*100:.1f}%)")
    
    if unmatched_count > 0:
        print(f"\n🔄 Creating receipts for {unmatched_count} unmatched banking debits...")
        
        # Pre-load existing receipt hashes
        cur.execute("SELECT source_hash FROM receipts WHERE source_hash IS NOT NULL")
        existing_hashes = {row[0] for row in cur.fetchall()}
        
        created = 0
        skipped = 0
        
        for txn_id, account, date, desc, debit, status in all_debits:
            if status == 'Matched':
                continue
            
            # Generate hash
            source_hash = generate_hash(date, desc, float(debit))
            
            # Check if receipt exists
            if source_hash in existing_hashes:
                # Link existing receipt
                cur.execute("SELECT receipt_id FROM receipts WHERE source_hash = %s", (source_hash,))
                receipt = cur.fetchone()
                if receipt:
                    receipt_id = receipt[0]
                    # Create link if not exists
                    cur.execute("""
                        INSERT INTO banking_receipt_matching_ledger (
                            banking_transaction_id, receipt_id, match_date,
                            match_type, match_status, match_confidence, 
                            notes, created_by
                        ) VALUES (%s, %s, CURRENT_DATE, 'auto_generated', 
                                 'matched', '100', 
                                 'Auto-linked from existing receipt', 'system')
                        ON CONFLICT DO NOTHING
                    """, (txn_id, receipt_id))
                skipped += 1
            else:
                # Create new receipt
                vendor = extract_vendor_from_description(desc)
                category = categorize_transaction(desc)
                gst, net = calculate_gst(float(debit))
                
                # Map account to bank account ID
                account_map = {
                    '0228362': 1,     # CIBC main
                    '1615': 1,        # CIBC overdraft
                    '903990106011': 2, # Scotia
                    '3648117': 1,     # Merchant (treat as CIBC)
                    '8314462': 1,     # Other (treat as CIBC)
                }
                mapped_account = account_map.get(account, 1)
                
                cur.execute("""
                    INSERT INTO receipts (
                        receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
                        description, category, created_from_banking, 
                        mapped_bank_account_id, source_hash
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, %s, %s)
                    RETURNING receipt_id
                """, (date, vendor, debit, gst, net, desc, category, mapped_account, source_hash))
                
                receipt_id = cur.fetchone()[0]
                existing_hashes.add(source_hash)
                
                # Create banking link
                cur.execute("""
                    INSERT INTO banking_receipt_matching_ledger (
                        banking_transaction_id, receipt_id, match_date,
                        match_type, match_status, match_confidence, 
                        notes, created_by
                    ) VALUES (%s, %s, CURRENT_DATE, 'auto_generated', 
                             'matched', '100', 
                             'Auto-created from banking transaction', 'system')
                """, (txn_id, receipt_id))
                
                created += 1
        
        conn.commit()
        print(f"✅ Created: {created} receipts")
        print(f"⏭️  Skipped: {skipped} (existing receipts linked)")
    
    # Now export to Excel
    print(f"\n📊 Exporting to Excel...")
    
    # Get all receipts for 2012
    cur.execute("""
        SELECT 
            r.receipt_id,
            r.receipt_date,
            r.vendor_name,
            r.gross_amount,
            r.gst_amount,
            r.net_amount,
            r.category,
            r.description,
            r.created_from_banking,
            r.mapped_bank_account_id,
            CASE 
                WHEN r.mapped_bank_account_id = 1 THEN 'CIBC'
                WHEN r.mapped_bank_account_id = 2 THEN 'Scotia'
                ELSE 'Other'
            END as bank_name,
            CASE 
                WHEN EXISTS (
                    SELECT 1 FROM banking_receipt_matching_ledger bm 
                    WHERE bm.receipt_id = r.receipt_id
                ) THEN 'Linked'
                ELSE 'Unlinked'
            END as link_status
        FROM receipts r
        WHERE EXTRACT(YEAR FROM r.receipt_date) = 2012
        ORDER BY r.receipt_date, r.receipt_id
    """)
    
    receipts_data = cur.fetchall()
    receipts_df = pd.DataFrame(receipts_data, columns=[
        'Receipt ID', 'Date', 'Vendor', 'Gross Amount', 'GST', 'Net Amount',
        'Category', 'Description', 'Auto Created', 'Bank ID', 'Bank Name', 'Link Status'
    ])
    
    # Get banking transactions by account
    accounts = ['0228362', '1615', '903990106011', '3648117', '8314462']
    account_names = {
        '0228362': 'CIBC Main',
        '1615': 'CIBC Overdraft',
        '903990106011': 'Scotia Bank',
        '3648117': 'Merchant',
        '8314462': 'Other'
    }
    
    excel_file = f'2012_Banking_Receipts_Reconciliation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    
    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        # Sheet 1: Receipts summary (first sheet)
        receipts_df.to_excel(writer, sheet_name='Receipts 2012', index=False)
        
        # Sheets 2+: Each banking account
        for account in accounts:
            cur.execute("""
                SELECT 
                    bt.transaction_id,
                    bt.transaction_date,
                    bt.description,
                    bt.debit_amount,
                    bt.credit_amount,
                    bt.balance,
                    CASE 
                        WHEN EXISTS (
                            SELECT 1 FROM banking_receipt_matching_ledger bm 
                            WHERE bm.banking_transaction_id = bt.transaction_id
                        ) THEN 'Has Receipt'
                        WHEN bt.debit_amount > 0 THEN 'Missing Receipt'
                        ELSE 'Credit (No Receipt Needed)'
                    END as receipt_status,
                    COALESCE(r.receipt_id, NULL) as receipt_id,
                    COALESCE(r.vendor_name, '') as receipt_vendor,
                    COALESCE(r.category, '') as receipt_category
                FROM banking_transactions bt
                LEFT JOIN banking_receipt_matching_ledger bm ON bt.transaction_id = bm.banking_transaction_id
                LEFT JOIN receipts r ON bm.receipt_id = r.receipt_id
                WHERE bt.account_number = %s
                AND EXTRACT(YEAR FROM bt.transaction_date) = 2012
                ORDER BY bt.transaction_date, bt.transaction_id
            """, (account,))
            
            account_data = cur.fetchall()
            if account_data:
                account_df = pd.DataFrame(account_data, columns=[
                    'Txn ID', 'Date', 'Description', 'Debit', 'Credit', 'Balance',
                    'Receipt Status', 'Receipt ID', 'Receipt Vendor', 'Receipt Category'
                ])
                
                sheet_name = account_names.get(account, account)[:31]  # Excel limit
                account_df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    print(f"✅ Excel exported: {excel_file}")
    
    # Final summary
    print(f"\n" + "=" * 100)
    print(f"SUMMARY:")
    print(f"  Total 2012 Receipts: {len(receipts_df)}")
    print(f"  Banking Debits Covered: {matched_count}/{total_debits}")
    print(f"  Excel File: {excel_file}")
    print(f"=" * 100)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
