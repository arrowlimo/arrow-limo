#!/usr/bin/env python3
"""
Create receipts for ALL Scotia Bank 2012 transactions.
"""

import psycopg2
import os
import re
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def calculate_gst(gross_amount, tax_rate=0.05):
    """Calculate GST that is INCLUDED in the gross amount (Alberta 5%)."""
    gross = float(gross_amount)
    gst_amount = gross * tax_rate / (1 + tax_rate)
    net_amount = gross - gst_amount
    return round(gst_amount, 2), round(net_amount, 2)

def extract_vendor_name(description):
    """Extract clean vendor name from transaction description."""
    if not description:
        return "UNKNOWN VENDOR"
    
    desc = description.strip()
    
    # Clean common patterns
    desc = re.sub(r'^CHQ\s+\d+\s*', '', desc, flags=re.IGNORECASE)
    desc = re.sub(r'^CHEQUE\s+\d+\s*', '', desc, flags=re.IGNORECASE)
    desc = re.sub(r'POINT OF SALE\s*-?\s*', '', desc, flags=re.IGNORECASE)
    desc = re.sub(r'RED DEER\s*,?\s*AB', '', desc, flags=re.IGNORECASE)
    desc = re.sub(r'#\d+', '', desc)  # Remove location codes
    desc = re.sub(r'\(C-STOR\)', '', desc, flags=re.IGNORECASE)
    desc = re.sub(r'\s+', ' ', desc).strip()
    
    if not desc or desc.upper() in ['CHQ', 'CHEQUE', '']:
        return "UNKNOWN PAYEE (CHEQUE)"
    
    return desc

def determine_category(description):
    """Determine receipt category from transaction description."""
    if not description:
        return "Unknown"
    
    desc = description.upper()
    
    # Liquor/Entertainment
    if any(keyword in desc for keyword in ['LIQUOR', 'BEER', 'WINE', 'BAR', 'PUB', 'RESTAURANT']):
        return "Liquor/Entertainment"
    
    # Fuel
    if any(keyword in desc for keyword in ['PETRO', 'SHELL', 'MOHAWK', 'GAS', 'FUEL', 'CENTEX', 'ESSO', 'HUSKY', "RUN'N ON EMPTY", 'RUN N ON EMPTY']):
        return "Fuel"
    
    # Supplies
    if any(keyword in desc for keyword in ['GNC', 'SHOPPERS', 'DRUG MART', 'STAPLES', 'CANADIAN TIRE', 'PARTS SOURCE']):
        return "Supplies"
    
    # Vehicle Rental/Maintenance
    if any(keyword in desc for keyword in ['TRUCK', 'RENTAL', 'ACE', 'HEFFNER', 'AUTO']):
        return "Vehicle Rental/Maintenance"
    
    # Bank Fees
    if any(keyword in desc for keyword in ['OD FEE', 'OVERDRAWN', 'SERVICE CHARGE', 'NSF FEE', 'NSF CHECK']):
        return "Bank Fees"
    
    # Income - Card Payments
    if any(keyword in desc for keyword in ['DEPOSIT', 'VCARD', 'MCARD', 'ACARD', 'DCARD']):
        return "Income - Card Payments"
    
    # Insurance
    if any(keyword in desc for keyword in ['INSURANCE', 'JEVCO']):
        return "Insurance"
    
    # Default for cheques and unknown
    if 'CHQ' in desc or 'CHEQUE' in desc:
        return "Unknown"
    
    return "Unknown"

def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    try:
        # First, check coverage by month
        print("=" * 80)
        print("SCOTIA BANK 2012 RECEIPT COVERAGE BY MONTH")
        print("=" * 80)
        
        cur.execute("""
            SELECT 
                EXTRACT(MONTH FROM b.transaction_date) as month,
                COUNT(b.transaction_id) as total_transactions,
                COUNT(r.receipt_id) as with_receipts,
                COUNT(b.transaction_id) - COUNT(r.receipt_id) as without_receipts
            FROM banking_transactions b
            LEFT JOIN receipts r ON r.banking_transaction_id = b.transaction_id
            WHERE b.bank_id = 2
                AND EXTRACT(YEAR FROM b.transaction_date) = 2012
            GROUP BY EXTRACT(MONTH FROM b.transaction_date)
            ORDER BY month
        """)
        
        months_data = cur.fetchall()
        total_missing = 0
        for row in months_data:
            month, total, with_receipts, without = row
            rate = (with_receipts / total * 100) if total > 0 else 0
            print(f"Month {int(month):02d}: {total:5} total | {with_receipts:5} receipts | {without:5} MISSING | {rate:5.1f}% matched")
            total_missing += without
        
        print()
        print(f"Total missing across all 2012: {total_missing}")
        print()
        
        # Get transactions without receipts
        cur.execute("""
            SELECT 
                b.transaction_id,
                b.transaction_date,
                COALESCE(b.debit_amount, 0) as debit,
                COALESCE(b.credit_amount, 0) as credit,
                b.description
            FROM banking_transactions b
            LEFT JOIN receipts r ON r.banking_transaction_id = b.transaction_id
            WHERE b.bank_id = 2
                AND EXTRACT(YEAR FROM b.transaction_date) = 2012
                AND r.receipt_id IS NULL
            ORDER BY b.transaction_date, b.transaction_id
        """)
        
        transactions = cur.fetchall()
        print(f"Found {len(transactions)} transactions without receipts")
        print()
        
        if not transactions:
            print("✅ All Scotia Bank 2012 transactions already have receipts!")
            return
        
        # Get next receipt_id
        cur.execute("SELECT COALESCE(MAX(receipt_id), 0) + 1 FROM receipts")
        next_receipt_id = cur.fetchone()[0]
        
        created_count = 0
        skipped_count = 0
        
        for tx_id, tx_date, debit, credit, description in transactions:
            # Calculate amount and determine type
            amount = debit if debit > 0 else credit
            is_income = credit > 0
            
            # Skip zero amounts
            if amount == 0:
                skipped_count += 1
                continue
            
            vendor_name = extract_vendor_name(description)
            category = determine_category(description)
            
            if is_income:
                # Income: no GST
                gross_amount = amount
                gst_amount = 0.00
                net_amount = amount
            else:
                # Expense: calculate GST (included in amount)
                gst_amount, net_amount = calculate_gst(amount)
                gross_amount = amount
            
            # Insert receipt
            cur.execute("""
                INSERT INTO receipts (
                    receipt_id, receipt_date, vendor_name, 
                    gross_amount, gst_amount, net_amount, 
                    category, banking_transaction_id, 
                    mapped_bank_account_id, created_from_banking
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                next_receipt_id,
                tx_date,
                vendor_name,
                gross_amount,
                gst_amount,
                net_amount,
                category,
                tx_id,
                2,  # Scotia Bank
                True
            ))
            
            created_count += 1
            tx_type_label = "INCOME " if is_income else "EXPENSE"
            print(f"✅ Receipt {next_receipt_id} | TX {tx_id:6} | {tx_date} | {tx_type_label} | ${amount:10,.2f} | {vendor_name[:40]}")
            
            next_receipt_id += 1
        
        # Commit all changes
        conn.commit()
        
        print()
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"✅ Created receipts: {created_count}")
        print(f"⚠️  Skipped (zero amount): {skipped_count}")
        print("✅ ALL CHANGES COMMITTED")
        
        # Verify
        cur.execute("""
            SELECT COUNT(*)
            FROM banking_transactions b
            LEFT JOIN receipts r ON r.banking_transaction_id = b.transaction_id
            WHERE b.bank_id = 2
                AND EXTRACT(YEAR FROM b.transaction_date) = 2012
                AND r.receipt_id IS NULL
                AND (COALESCE(b.debit_amount, 0) + COALESCE(b.credit_amount, 0)) != 0
        """)
        remaining = cur.fetchone()[0]
        print()
        print(f"Verification: {remaining} Scotia 2012 transactions still need receipts")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ ERROR: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
