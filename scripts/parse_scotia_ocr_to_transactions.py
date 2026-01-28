#!/usr/bin/env python3
"""
Parse OCR'd Scotia Bank statements and extract transactions.

This parses the combined OCR output from ocr_scotia_jpg_files.py
and extracts transaction data for import into banking_transactions.
"""

import re
import psycopg2
import hashlib
from datetime import datetime, date
from decimal import Decimal
import argparse

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def clean_ocr_text(text):
    """Clean common OCR errors."""
    # Common character substitutions
    text = text.replace('OOOO', '0000')
    text = text.replace('QOOO', '0000')
    text = text.replace('OOO', '000')
    text = text.replace('QQQ', '000')
    text = text.replace('eee', 'CHASE')
    text = text.replace('ae', 'CHASE')
    text = text.replace('EPOSIT', 'DEPOSIT')
    text = text.replace('ETURNED', 'RETURNED')
    text = text.replace('OINT', 'POINT')
    text = text.replace('HQ', 'CHQ')
    text = text.replace('Bo hace', 'SERVICE')
    text = text.replace('SEF', 'NSF')
    
    return text

def parse_amount_from_lines(lines, start_idx):
    """
    Parse amount from Scotia format where dollars and cents are on separate lines.
    Returns (amount, end_idx) or None.
    
    Format example:
    594      <- dollars
    98       <- cents
    """
    if start_idx + 1 >= len(lines):
        return None
    
    line1 = lines[start_idx].strip()
    line2 = lines[start_idx + 1].strip()
    
    # Clean OCR errors
    def clean_ocr(s):
        s = s.replace('|', '1')
        s = s.replace('!', '1')
        s = s.replace('o', '0')
        s = s.replace('O', '0')
        s = s.replace('l', '1')
        s = s.replace('I', '1')
        s = s.replace('S', '5')
        s = s.replace(',', '')
        s = s.replace(' ', '')
        return s
    
    # Check for trailing minus (debit)
    is_debit = line1.endswith('-') or line2.endswith('-')
    
    line1 = clean_ocr(line1.rstrip('-'))
    line2 = clean_ocr(line2.rstrip('-'))
    
    # Both should be numeric
    if line1.isdigit() and line2.isdigit():
        # Cents should be 2 digits, pad if needed
        cents = line2.zfill(2)
        amount_str = f"{line1}.{cents}"
        try:
            amount = float(amount_str)
            return ((-amount if is_debit else amount), start_idx + 2)
        except:
            pass
    
    # Fallback: try single line with decimal
    line = clean_ocr(lines[start_idx].strip().rstrip('-'))
    if '.' in line:
        try:
            amount = float(line)
            return ((-amount if is_debit else amount), start_idx + 1)
        except:
            pass
    
    return None

def extract_date_from_lines(lines, start_idx):
    """
    Extract date from Scotia format where MM and DD are on separate lines.
    Returns (month, day, end_idx) or None.
    """
    # Look for two consecutive lines with small numbers (month and day)
    if start_idx + 1 < len(lines):
        line1 = lines[start_idx].strip()
        line2 = lines[start_idx + 1].strip()
        
        # Try to parse as MM on first line, DD on second
        if line1.isdigit() and line2.isdigit():
            month = int(line1)
            day = int(line2)
            if 1 <= month <= 12 and 1 <= day <= 31:
                return (month, day, start_idx + 2)
    
    # Also handle MM/DD on same line as fallback
    for i in range(start_idx, min(start_idx + 5, len(lines))):
        line = lines[i].strip()
        match = re.search(r'(\d{1,2})/(\d{1,2})', line)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            if 1 <= month <= 12 and 1 <= day <= 31:
                return (month, day, i + 1)
    
    return None

def parse_ocr_file(file_path):
    """Parse OCR'd Scotia statement and extract transactions.
    
    Statement format (columns left to right):
    1. Description (may span multiple lines)
    2. Withdrawal/Debit amount (single number, no decimal, divide by 100)
    3. Deposit/Credit amount (OR the withdrawal column has it)
    4. Date (4-digit MMDD format like 0110, 1107)
    5. Balance (single number with optional -, divide by 100)
    
    OCR extracts these as separate lines in sequence.
    Transaction pattern: Description → Amount → Date → Balance
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Clean OCR errors
    content = clean_ocr_text(content)
    
    lines = [line.strip() for line in content.split('\n')]
    
    all_transactions = []
    current_year = 2013
    last_month = None
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        if not line or line.startswith('=') or line.startswith('FILE:'):
            i += 1
            continue
        
        # Skip account numbers
        if re.match(r'^\d{12,}\s+[O0Q]{4,}', line):
            i += 1
            continue
        
        # Look for transaction keywords (description start)
        if any(keyword in line.upper() for keyword in [
            'DEPOSIT', 'EPOSIT', 'PURCHASE', 'PAYMENT', 'WITHDRAWAL', 'TRANSFER',
            'CHEQUE', 'CHQ', 'VISA', 'MCARD', 'AMEX', 'MEMO', 'CHARGE', 
            'BALANCE FORWARD', 'DEBIT', 'CREDIT', 'LEASE', 'INSURANCE',
            'SERVICE', 'ABM', 'AUTO', 'RETURNED', 'OINT OF SALE'
        ]):
            # Found description start
            description_parts = [line]
            j = i + 1
            
            # Collect multi-line description (up to 3 more lines)
            while j < len(lines) and j < i + 4:
                next_line = lines[j]
                
                if not next_line:
                    j += 1
                    continue
                
                # Stop at account number
                if re.match(r'^\d{12,}', next_line):
                    break
                
                # Stop at pure number (amount or date candidate)
                if re.match(r'^\d+\.?\d*-?$', next_line.replace(' ', '').replace('/', '')):
                    break
                
                # Continue if mostly alphabetic
                if sum(c.isalpha() for c in next_line) > len(next_line) / 2:
                    description_parts.append(next_line)
                    j += 1
                else:
                    break
            
            description = ' '.join(description_parts)
            
            # Now look for: amount → date pattern
            trans_amount = None
            trans_date = None
            
            # Look ahead up to 10 lines for amount and date
            while j < len(lines) and j < i + 12:
                curr_line = lines[j]
                
                if not curr_line:
                    j += 1
                    continue
                
                # Skip account numbers
                if re.match(r'^\d{12,}', curr_line):
                    j += 1
                    continue
                
                # Check for date (4-digit MMDD)
                if curr_line.isdigit() and len(curr_line) == 4:
                    month = int(curr_line[:2])
                    day = int(curr_line[2:])
                    
                    if 1 <= month <= 12 and 1 <= day <= 31:
                        # Adjust year if month wrapped
                        if last_month and month < last_month:
                            current_year += 1
                        
                        try:
                            trans_date = date(current_year, month, day)
                            last_month = month
                            j += 1
                            break  # Got date, transaction complete
                        except:
                            pass
                
                # Check for amount (number that's not account number or date)
                # Amounts are 3-6 digits typically
                if (curr_line.replace('-', '').replace('/', '').isdigit() and 
                    3 <= len(curr_line.replace('-', '').replace('/', '')) <= 7):
                    
                    clean_num = curr_line.replace('/', '').replace('-', '')
                    
                    # Make sure it's not a valid date
                    is_date = False
                    if len(clean_num) == 4:
                        try_month = int(clean_num[:2])
                        try_day = int(clean_num[2:])
                        if 1 <= try_month <= 12 and 1 <= try_day <= 31:
                            is_date = True
                    
                    if not is_date and trans_amount is None:
                        try:
                            # Convert to dollars (divide by 100)
                            amount_val = float(clean_num) / 100.0
                            
                            # Determine if debit or credit based on description
                            if any(kw in description.upper() for kw in ['EPOSIT', 'DEPOSIT', 'CREDIT MEMO', 'CR ']):
                                trans_amount = amount_val  # Credit (positive)
                            else:
                                trans_amount = -amount_val  # Debit (negative)
                        except:
                            pass
                
                j += 1
            
            # Create transaction if we have date and amount
            if trans_date and trans_amount is not None:
                all_transactions.append({
                    'date': trans_date,
                    'description': description,
                    'amount': trans_amount
                })
            
            i = j
        else:
            i += 1
    
    return all_transactions

def categorize_transaction(description):
    """Categorize transaction based on description."""
    desc_upper = description.upper()
    
    # Bank fees
    if any(x in desc_upper for x in ['SERVICE CHARGE', 'NSF', 'OVERDRAWN']):
        return 'BANK_FEE'
    
    # Merchant settlements
    if 'DEP CR' in desc_upper and any(x in desc_upper for x in ['CHASE', 'PAYMENTECH']):
        return 'MERCHANT_SETTLEMENT_CREDIT'
    
    # Deposits
    if 'DEPOSIT' in desc_upper and 'CHASE' not in desc_upper:
        return 'REVENUE_DEPOSIT'
    
    # POS purchases
    if 'POINT OF SALE' in desc_upper or any(x in desc_upper for x in ['SHOPPERS', 'FAS GAS', 'CINEPLEX']):
        return 'EXPENSE_SUPPLIES'
    
    # Withdrawals
    if 'WITHDRAWAL' in desc_upper or 'ABM' in desc_upper:
        return 'CASH_WITHDRAWAL'
    
    # Credit card payments
    if 'AMEX' in desc_upper and 'BANK' in desc_upper:
        return 'CREDIT_CARD_PAYMENT'
    
    # Cheques
    if 'CHQ' in desc_upper or 'CHEQUE' in desc_upper:
        if 'RETURNED' in desc_upper and 'NSF' in desc_upper:
            return 'JOURNAL_ENTRY_REVERSAL'
        return 'EXPENSE_CHEQUE'
    
    # Memos
    if 'MEMO' in desc_upper:
        return 'JOURNAL_ENTRY'
    
    return 'UNCATEGORIZED'

def extract_vendor(description):
    """Extract vendor name from description."""
    desc = description.strip()
    
    if 'CHASE PAYMENTECH' in desc:
        return 'Chase Paymentech'
    
    if 'SHOPPERS DRUG MART' in desc:
        return 'Shoppers Drug Mart'
    
    if 'FAS GAS' in desc:
        return 'Fas Gas'
    
    if 'CINEPLEX' in desc:
        return 'Cineplex'
    
    if 'AMEX' in desc:
        return 'American Express'
    
    # Extract from POS purchases
    if 'POINT OF SALE' in desc:
        # Try to get vendor name
        parts = desc.split('PURCHASE')
        if len(parts) > 1:
            vendor = parts[1].strip().split('\n')[0]
            return vendor[:50] if vendor else None
    
    return None

def generate_hash(date, description, amount):
    """Generate deterministic hash for duplicate detection."""
    hash_input = f"{date}|{description}|{amount:.2f}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def main():
    parser = argparse.ArgumentParser(description='Parse Scotia OCR output')
    parser.add_argument('--write', action='store_true', help='Import to database')
    parser.add_argument('--input', default=r'L:\limo\data\scotia_ocr_output\scotia_all_pages_combined.txt',
                        help='OCR input file')
    args = parser.parse_args()
    
    print(f"\n{'='*80}")
    print(f"Scotia Bank OCR Parser")
    print(f"{'='*80}")
    print(f"Input: {args.input}")
    print(f"Mode: {'WRITE' if args.write else 'DRY RUN'}")
    
    # Parse OCR output
    transactions = parse_ocr_file(args.input)
    
    print(f"\nExtracted {len(transactions)} potential transactions")
    
    # Filter to transactions with both date and amount
    complete_transactions = [t for t in transactions if t['date'] and t['amount']]
    print(f"Complete transactions (date + amount): {len(complete_transactions)}")
    
    if not args.write:
        # Show sample transactions
        print(f"\nSample transactions:")
        for i, trans in enumerate(complete_transactions[:20], 1):
            amount_str = f"{trans['amount']:10.2f}"
            debit_credit = "D" if trans['amount'] < 0 else "C"
            print(f"  {i:2d}. {trans['date']} | {amount_str} {debit_credit} | {trans['description'][:60]}")
        
        if len(complete_transactions) > 20:
            print(f"  ... and {len(complete_transactions) - 20} more")
        
        print(f"\n{'='*80}")
        print(f"Run with --write to import to database")
        return
    
    # Import to database
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get existing hashes
    cur.execute("""
        SELECT source_hash FROM banking_transactions
        WHERE account_number = '903990106011'
        AND source_hash IS NOT NULL
    """)
    existing_hashes = {row[0] for row in cur.fetchall()}
    
    imported = 0
    skipped = 0
    
    for trans in complete_transactions:
        # Determine debit/credit
        debit_amt = abs(trans['amount']) if trans['amount'] < 0 else None
        credit_amt = trans['amount'] if trans['amount'] > 0 else None
        
        # Generate hash
        source_hash = generate_hash(trans['date'], trans['description'], 
                                    abs(trans['amount']))
        
        if source_hash in existing_hashes:
            skipped += 1
            continue
        
        # Categorize and extract vendor
        category = categorize_transaction(trans['description'])
        vendor = extract_vendor(trans['description'])
        
        cur.execute("""
            INSERT INTO banking_transactions (
                account_number, transaction_date, description,
                debit_amount, credit_amount, category, vendor_extracted, source_hash
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, ('903990106011', trans['date'], trans['description'],
              debit_amt, credit_amt, category, vendor, source_hash))
        
        imported += 1
        existing_hashes.add(source_hash)
    
    conn.commit()
    
    print(f"\n{'='*80}")
    print(f"Import Summary:")
    print(f"  Imported: {imported}")
    print(f"  Skipped (duplicates): {skipped}")
    print(f"{'='*80}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
