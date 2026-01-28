"""
COMPREHENSIVE Scotia Bank 2012 PDF Parser with Full Transaction Extraction

This script:
1. Extracts all transaction lines from PDF
2. Parses each line to extract: description, withdrawal, deposit, date, balance
3. Applies OCR correction to amounts and dates
4. Fills missing dates with last known date
5. Validates running balance
6. Exports to CSV for database import
"""
import pdfplumber
import re
from decimal import Decimal
from datetime import datetime, date
import csv

def fix_ocr_amount(text):
    """Fix OCR corruption in amounts."""
    if not text:
        return None
    
    # Remove all whitespace
    text = text.replace(' ', '').replace('\t', '').replace('\n', '')
    
    # Fix corrupted characters
    text = text.replace('!', '.').replace(':', '.').replace('i', '.')
    text = text.replace('b', '0').replace('D', '0').replace('O', '0')
    text = text.replace('l', '1').replace('I', '1').replace('|', '1')
    text = text.replace('r', '').replace('V', '').replace('v', '').replace('..', '.')
    text = text.replace('F', '').replace('f', '').replace('°', '0').replace('�', '').replace('o', '0')
    text = text.replace('j', '').replace('C', '').replace('c', '')
    
    # Remove non-numeric and non-decimal point characters
    text = re.sub(r'[^0-9.]', '', text)
    
    if not text or text == '.':
        return None
    
    # Handle multiple dots
    parts = text.split('.')
    if len(parts) > 2:
        dollars = ''.join(parts[:-1])
        cents = parts[-1]
        text = f"{dollars}.{cents}"
    
    # Ensure exactly 2 decimal places
    if '.' in text:
        parts = text.split('.')
        dollars = parts[0] if parts[0] else '0'
        cents = parts[1][:2] if len(parts) > 1 else '00'
        text = f"{dollars}.{cents.zfill(2)}"
    else:
        # Assume last 2 digits are cents
        if len(text) >= 3:
            text = f"{text[:-2]}.{text[-2:]}"
        elif len(text) == 2:
            text = f"0.{text}"
        elif len(text) == 1:
            text = f"0.0{text}"
        else:
            return None
    
    try:
        return Decimal(text)
    except:
        return None

def fix_ocr_date(text, year=2012):
    """Fix OCR corruption in date (MM/DD format)."""
    if not text:
        return None
    
    # Remove whitespace
    text = text.replace(' ', '').replace('\t', '')
    
    # Fix corrupted characters
    text = text.replace('!', '').replace(':', '').replace('i', '').replace('.', '')
    text = text.replace('b', '0').replace('D', '0').replace('O', '0')
    text = text.replace('l', '1').replace('I', '1').replace('|', '1')
    text = text.replace('p', '').replace('P', '').replace('°', '0').replace('o', '0')
    
    # Remove non-numeric
    text = re.sub(r'[^0-9]', '', text)
    
    if not text:
        return None
    
    # Parse as MMDD or MDD
    try:
        if len(text) == 3:
            month = text[0]
            day = text[1:]
        elif len(text) == 4:
            month = text[:2]
            day = text[2:]
        else:
            return None
        
        month = month.zfill(2)
        day = day.zfill(2)
        
        return datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d").date()
    except:
        return None

def parse_transaction_line(line, page_num):
    """
    Parse a single transaction line to extract fields.
    
    Line format (approximate):
    DESCRIPTION [AMOUNT1] [AMOUNT2] [DATE] [BALANCE]
    
    Returns dict with: description, withdrawal, deposit, date, balance
    """
    result = {
        'page': page_num,
        'raw_line': line,
        'description': None,
        'withdrawal': None,
        'deposit': None,
        'date': None,
        'balance': None
    }
    
    # Skip header lines
    if any(x in line.upper() for x in ['SCOTIABANK', 'ACCOUNT NUMBER', 'STATEMENT OF', 
                                        'WITHDRAWAL/DEBITS', 'DEPOSIT/CREDIT', 
                                        'NO. OF', 'DEBITS', 'CREDITS', 'BALANCE FORWARD']):
        return None
    
    # Extract description (first part before amounts)
    # Look for transaction type keywords
    desc_match = re.search(r'(.*?)(DEPOSIT|WITHDRAWAL|PURCHASE|CHQ|DRAFT|REFUND)', line, re.IGNORECASE)
    if desc_match:
        desc_type = desc_match.group(2).upper()
        # Get everything from start to just after transaction type
        desc_end_pos = desc_match.end()
        
        # Include vendor/location after transaction type
        remaining = line[desc_end_pos:].strip()
        vendor_match = re.search(r'^[A-Z0-9\s\-#&.,]+', remaining)
        if vendor_match:
            vendor = vendor_match.group(0).strip()
            # Remove amount-like patterns from vendor
            vendor = re.sub(r'\d{2,}', '', vendor).strip()
            result['description'] = f"{desc_type} {vendor}".strip()
            remaining = remaining[vendor_match.end():].strip()
        else:
            result['description'] = desc_type
            
        # Now parse amounts and date from remaining text
        # Find all number-like patterns
        amount_patterns = re.findall(r'[\d!:iblIDO°oFfjCcVvrp\s]{2,}', remaining)
        
        # Try to identify which are amounts vs date vs balance
        parsed_numbers = []
        for pattern in amount_patterns:
            # Try as amount
            amt = fix_ocr_amount(pattern)
            if amt and amt > 0:
                parsed_numbers.append(('amount', amt, pattern))
            else:
                # Try as date
                dt = fix_ocr_date(pattern)
                if dt:
                    parsed_numbers.append(('date', dt, pattern))
        
        # Assign parsed numbers to fields
        # Last number is likely balance
        # Date is usually near the end (M/D format, smaller number)
        # Amounts are withdrawal or deposit
        
        if len(parsed_numbers) >= 1:
            # Heuristic: Last amount-type is balance (usually large)
            # Second-to-last might be amount
            # Date is usually between amount and balance
            
            amounts = [p for p in parsed_numbers if p[0] == 'amount']
            dates = [p for p in parsed_numbers if p[0] == 'date']
            
            if dates:
                result['date'] = dates[-1][1]  # Last date
            
            if amounts:
                # Balance is likely the largest amount at the end
                # Transaction amount is smaller, earlier
                if len(amounts) == 1:
                    # Only one amount - could be transaction or balance
                    # If date exists, amount before date is transaction, after is balance
                    if dates:
                        result['balance'] = amounts[0][1]
                    else:
                        # No date, assume this is transaction amount
                        if 'DEPOSIT' in result['description'].upper():
                            result['deposit'] = amounts[0][1]
                        elif 'WITHDRAWAL' in result['description'].upper() or 'PURCHASE' in result['description'].upper():
                            result['withdrawal'] = amounts[0][1]
                elif len(amounts) >= 2:
                    # Multiple amounts: assume first is transaction, last is balance
                    if 'DEPOSIT' in result['description'].upper():
                        result['deposit'] = amounts[0][1]
                    elif 'WITHDRAWAL' in result['description'].upper() or 'PURCHASE' in result['description'].upper() or 'CHQ' in result['description'].upper():
                        result['withdrawal'] = amounts[0][1]
                    result['balance'] = amounts[-1][1]
    
    return result if result['description'] else None

def extract_all_transactions(pdf_path):
    """Extract all transactions from PDF."""
    transactions = []
    
    print(f"Opening PDF: {pdf_path}")
    
    with pdfplumber.open(pdf_path) as pdf:
        print(f"Total pages: {len(pdf.pages)}")
        
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if not text:
                continue
            
            lines = text.split('\n')
            
            for line in lines:
                # Look for transaction lines
                if any(x in line.upper() for x in ['DEPOSIT', 'WITHDRAWAL', 'PURCHASE', 'CHQ', 'DRAFT', 'REFUND']):
                    txn = parse_transaction_line(line, page_num)
                    if txn:
                        transactions.append(txn)
    
    print(f"\nTotal transactions extracted: {len(transactions)}")
    return transactions

def fill_missing_dates(transactions):
    """Fill missing dates with previous known date."""
    last_date = None
    filled_count = 0
    
    for txn in transactions:
        if txn['date']:
            last_date = txn['date']
        elif last_date:
            txn['date'] = last_date
            filled_count += 1
    
    print(f"Filled {filled_count} missing dates")
    return transactions

def verify_running_balance(transactions):
    """Verify running balance calculations."""
    print("\nVerifying running balance...")
    
    if not transactions:
        print("No transactions to verify")
        return
    
    # Find first balance
    opening_balance = None
    for txn in transactions:
        if txn['balance']:
            opening_balance = txn['balance']
            print(f"Opening balance: ${opening_balance}")
            break
    
    if not opening_balance:
        print("WARNING: No opening balance found")
        return
    
    calculated_balance = opening_balance
    mismatches = 0
    
    for i, txn in enumerate(transactions):
        if not txn['balance']:
            continue
        
        # Update calculated balance
        if txn['deposit']:
            calculated_balance += txn['deposit']
        if txn['withdrawal']:
            calculated_balance -= txn['withdrawal']
        
        # Compare
        diff = abs(calculated_balance - txn['balance'])
        if diff > Decimal('0.01'):
            mismatches += 1
            if mismatches <= 5:  # Show first 5 mismatches
                print(f"  Mismatch at transaction {i+1}: calculated=${calculated_balance}, recorded=${txn['balance']}, diff=${diff}")
    
    print(f"Balance verification complete: {mismatches} mismatches")

def export_to_csv(transactions, output_path):
    """Export transactions to CSV."""
    print(f"\nExporting to CSV: {output_path}")
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['page', 'date', 'description', 'withdrawal', 'deposit', 'balance'])
        writer.writeheader()
        
        for txn in transactions:
            writer.writerow({
                'page': txn['page'],
                'date': txn['date'].strftime('%Y-%m-%d') if txn['date'] else '',
                'description': txn['description'] or '',
                'withdrawal': f"{txn['withdrawal']:.2f}" if txn['withdrawal'] else '',
                'deposit': f"{txn['deposit']:.2f}" if txn['deposit'] else '',
                'balance': f"{txn['balance']:.2f}" if txn['balance'] else ''
            })
    
    print(f"Export complete: {len(transactions)} transactions")

if __name__ == '__main__':
    pdf_path = r'L:\limo\pdf\2012\2012 scotiabank statements all.pdf'
    output_csv = r'L:\limo\data\scotia_2012_parsed_comprehensive.csv'
    
    print("="*100)
    print("SCOTIA BANK 2012 COMPREHENSIVE PDF PARSER")
    print("="*100)
    
    # Extract transactions
    transactions = extract_all_transactions(pdf_path)
    
    if not transactions:
        print("\nERROR: No transactions extracted!")
        exit(1)
    
    # Fill missing dates
    transactions = fill_missing_dates(transactions)
    
    # Show sample
    print("\n" + "="*100)
    print("SAMPLE TRANSACTIONS (First 10)")
    print("="*100)
    for i, txn in enumerate(transactions[:10], 1):
        print(f"\n{i}. {txn['description']}")
        print(f"   Page: {txn['page']}")
        print(f"   Date: {txn['date']}")
        print(f"   Withdrawal: ${txn['withdrawal']}" if txn['withdrawal'] else "")
        print(f"   Deposit: ${txn['deposit']}" if txn['deposit'] else "")
        print(f"   Balance: ${txn['balance']}" if txn['balance'] else "")
    
    # Verify balance
    verify_running_balance(transactions)
    
    # Export to CSV
    export_to_csv(transactions, output_csv)
    
    print("\n" + "="*100)
    print("PROCESSING COMPLETE")
    print("="*100)
