#!/usr/bin/env python3
"""
Import Scotia Bank Dec 2012 - Jan 2013 from Excel OCR export.

Handles the format where OCR has extracted text into Excel columns with:
- Description column
- Withdrawal/Debit column  
- Deposit/Credit column
- Date column (MM|DD format or similar)
- Balance column

Instructions:
1. Save the Excel file as CSV
2. Update TRANSACTIONS list below with the data
3. Run with --write flag to import
"""

import psycopg2
import hashlib
import re
from datetime import datetime, date
import argparse

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def generate_hash(date, description, amount):
    """Generate deterministic hash for duplicate detection."""
    hash_input = f"{date}|{description}|{amount:.2f}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def parse_date_from_ocr(date_str, year=2013):
    """
    Parse date from OCR format like '01|07', '1650|', etc.
    Returns date object or None if unparseable.
    """
    if not date_str:
        return None
    
    # Remove pipes and clean
    clean = date_str.replace('|', '').strip()
    
    # Try MM/DD format (like 0107 for 01/07)
    if len(clean) == 4 and clean.isdigit():
        month = int(clean[:2])
        day = int(clean[2:])
        if 1 <= month <= 12 and 1 <= day <= 31:
            return date(year, month, day)
    
    # Try MMDD format without leading zero (like 107 for 01/07)
    if len(clean) == 3 and clean.isdigit():
        month = int(clean[0])
        day = int(clean[1:])
        if 1 <= month <= 12 and 1 <= day <= 31:
            return date(year, month, day)
    
    return None

def parse_amount_from_ocr(amount_str):
    """
    Parse amount from OCR which may have various formats:
    '1650|', '42150.', '42150', '3B5!oo', etc.
    """
    if not amount_str:
        return None
    
    # Clean: remove pipes, spaces, common OCR errors
    clean = amount_str.replace('|', '').replace(' ', '').strip()
    clean = clean.replace('!', '1').replace('o', '0').replace('O', '0')
    clean = clean.replace('l', '1').replace('I', '1')
    
    # Remove trailing periods if they appear to be OCR artifacts
    if clean.endswith('.') and '.' not in clean[:-1]:
        clean = clean[:-1]
    
    # Try to parse as float
    try:
        return float(clean)
    except:
        return None

def extract_vendor_from_description(description):
    """Extract vendor name from transaction description."""
    if not description:
        return None
    
    desc = description.strip()
    
    # Merchant deposits
    if 'MCARD DEP CR' in desc or 'VISA DEP CR' in desc or 'DEBIT CD DEP CR' in desc:
        if 'CHASE' in desc or 'PAYMENTECH' in desc:
            return 'Chase Paymentech'
        return 'Merchant Deposit'
    
    # POS purchases
    if 'POINT OF SALE PURCHASE' in desc or 'CINEPLEX' in desc:
        # Extract vendor name from description
        parts = desc.split()
        if 'CINEPLEX' in desc:
            return 'Cineplex'
        # Return description as-is for now
        return desc
    
    # Rent/Lease
    if 'RENT/LEASES' in desc or 'AUTO LEASE' in desc:
        if 'HEFFNER' in desc:
            return 'Heffner Auto'
        if 'ACE TRUCK' in desc:
            return 'ACE Truck Rentals'
        return 'Lease Payment'
    
    # NSF and service charges
    if 'NSF' in desc or 'SERVICE CHARGE' in desc or 'OVERDRAWN' in desc:
        return 'Scotia Bank'
    
    # AMEX payments
    if 'AMEX' in desc:
        return 'American Express'
    
    # Cheques
    if 'CHQ' in desc or 'CHEQUE' in desc:
        match = re.search(r'(\d+)', desc)
        if match:
            return f'Cheque {match.group(1)}'
    
    return None

def categorize_transaction(description):
    """Categorize transaction based on description patterns."""
    desc_upper = description.upper()
    
    # Bank fees
    if any(x in desc_upper for x in ['SERVICE CHARGE', 'OVERDRAWN', 'NSF']):
        return 'BANK_FEE'
    
    # Returned items
    if 'RETURNED' in desc_upper and 'NSF' in desc_upper:
        return 'JOURNAL_ENTRY_REVERSAL'
    
    # Merchant settlements
    if 'DEP CR' in desc_upper and 'CHASE' in desc_upper:
        return 'MERCHANT_SETTLEMENT_CREDIT'
    
    # Deposits (general)
    if 'DEPOSIT' in desc_upper and 'MERCHANT' not in desc_upper:
        return 'REVENUE_DEPOSIT'
    
    # Rent/Lease
    if 'RENT' in desc_upper or 'LEASE' in desc_upper:
        return 'EXPENSE_LEASE'
    
    # Debit/Credit Memos
    if 'DEBIT MEMO' in desc_upper or 'CREDIT MEMO' in desc_upper:
        if 'CASH' in desc_upper:
            return 'JOURNAL_ENTRY'
        return 'JOURNAL_ENTRY'
    
    # POS purchases
    if 'POINT OF SALE' in desc_upper or 'CINEPLEX' in desc_upper:
        return 'EXPENSE_SUPPLIES'
    
    # ABM withdrawals
    if 'ABM WITHDRAWAL' in desc_upper:
        return 'CASH_WITHDRAWAL'
    
    # AMEX payments
    if 'AMEX' in desc_upper:
        return 'CREDIT_CARD_PAYMENT'
    
    # Cheques
    if 'CHQ' in desc_upper or 'CHEQUE' in desc_upper:
        return 'EXPENSE_CHEQUE'
    
    return 'UNCATEGORIZED'

# PASTE YOUR TRANSACTION DATA HERE
# Format: (date_string, description, withdrawal, deposit)
# Use the date column value as-is, script will parse it
TRANSACTIONS = [
    # Example from your OCR:
    # ('01|07', 'BALANCE FORWARD DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 594.98),
    
    # PASTE DATA BELOW THIS LINE
    
]

def main():
    parser = argparse.ArgumentParser(description='Import Scotia Dec 2012 - Jan 2013 from OCR')
    parser.add_argument('--write', action='store_true', help='Apply changes to database')
    parser.add_argument('--year', type=int, default=2013, help='Year for transactions (default: 2013)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check for existing hashes
    cur.execute("""
        SELECT source_hash FROM banking_transactions 
        WHERE account_number = '903990106011' 
        AND source_hash IS NOT NULL
    """)
    existing_hashes = {row[0] for row in cur.fetchall()}
    
    print(f"\n{'='*80}")
    print(f"Scotia Bank Dec 2012 - Jan 2013 Import")
    print(f"{'='*80}")
    print(f"Mode: {'WRITE' if args.write else 'DRY RUN'}")
    print(f"Existing transactions in DB: {len(existing_hashes)}")
    print(f"Transactions to process: {len(TRANSACTIONS)}")
    
    imported = 0
    skipped = 0
    errors = []
    
    for i, (date_str, description, withdrawal, deposit) in enumerate(TRANSACTIONS, 1):
        # Parse date
        trans_date = parse_date_from_ocr(date_str, args.year)
        if not trans_date:
            errors.append(f"Line {i}: Could not parse date '{date_str}'")
            continue
        
        # Parse amounts
        debit_amt = parse_amount_from_ocr(str(withdrawal)) if withdrawal else None
        credit_amt = parse_amount_from_ocr(str(deposit)) if deposit else None
        
        if not debit_amt and not credit_amt:
            errors.append(f"Line {i}: No valid amount found")
            continue
        
        # Determine which amount to use for hash
        hash_amount = debit_amt or credit_amt
        
        # Generate hash
        source_hash = generate_hash(trans_date, description, hash_amount)
        
        if source_hash in existing_hashes:
            skipped += 1
            continue
        
        # Extract vendor and category
        vendor = extract_vendor_from_description(description)
        category = categorize_transaction(description)
        
        if args.write:
            cur.execute("""
                INSERT INTO banking_transactions (
                    account_number, transaction_date, description,
                    debit_amount, credit_amount, vendor_extracted, category, source_hash
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, ('903990106011', trans_date, description, 
                  debit_amt, credit_amt, vendor, category, source_hash))
            imported += 1
            existing_hashes.add(source_hash)
        else:
            print(f"{trans_date} | {description[:50]:50s} | D:{debit_amt or 0:8.2f} C:{credit_amt or 0:8.2f} | {category}")
            imported += 1
    
    if args.write:
        conn.commit()
    
    print(f"\n{'='*80}")
    print(f"Summary:")
    print(f"  Imported: {imported}")
    print(f"  Skipped (duplicates): {skipped}")
    print(f"  Errors: {len(errors)}")
    
    if errors:
        print(f"\nErrors:")
        for error in errors[:10]:
            print(f"  {error}")
        if len(errors) > 10:
            print(f"  ... and {len(errors)-10} more")
    
    if not args.write:
        print(f"\nDRY RUN - No changes made. Run with --write to import.")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
