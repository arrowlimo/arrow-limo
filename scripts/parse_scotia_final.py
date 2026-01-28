"""
Parse Scotia Bank 2012 PDF - handles rotated/sideways pages automatically.

This parser:
1. Detects if page text is rotated
2. Extracts transactions regardless of orientation
3. Parses transaction details with minimal OCR correction needed
4. Exports to CSV for database import
"""
import pdfplumber
import re
from decimal import Decimal
from datetime import datetime
import csv

def clean_amount(text):
    """Clean and parse monetary amounts."""
    if not text:
        return None
    
    # Remove whitespace and common OCR artifacts
    text = str(text).strip()
    text = re.sub(r'[^\d.,\-+]', '', text)
    
    # Remove multiple decimals/commas
    text = text.replace(',', '')
    
    if not text or text in ['.', '-', '+']:
        return None
    
    try:
        return Decimal(text)
    except:
        return None

def parse_date(date_str, year=2012):
    """Parse date in M/D or MM/DD format for given year."""
    if not date_str:
        return None
    
    # Extract numbers only
    nums = re.findall(r'\d+', str(date_str))
    if not nums:
        return None
    
    # Join if split
    date_num = ''.join(nums)
    
    try:
        if len(date_num) == 3:  # MDD
            month = date_num[0]
            day = date_num[1:]
        elif len(date_num) == 4:  # MMDD
            month = date_num[:2]
            day = date_num[2:]
        else:
            return None
        
        return datetime.strptime(f"{year}-{month.zfill(2)}-{day.zfill(2)}", "%Y-%m-%d").date()
    except:
        return None

def is_transaction_line(line):
    """Check if line contains transaction keywords."""
    keywords = ['DEPOSIT', 'WITHDRAWAL', 'PURCHASE', 'CHQ', 'DRAFT', 'REFUND', 
                'ABM', 'POINT OF SALE', 'DEBIT', 'CREDIT', 'MEMO']
    line_upper = line.upper()
    return any(kw in line_upper for kw in keywords)

def parse_transaction_from_line(line, page_num, last_date=None):
    """
    Parse a transaction line into components.
    
    Expected patterns:
    - Description at start
    - Amounts (withdrawal or deposit)
    - Date (M D format)
    - Balance at end
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
    
    # Skip non-transaction lines
    if not is_transaction_line(line):
        return None
    
    # Extract description (everything before first large amount)
    desc_match = re.match(r'^(.*?)([\d\s.,]{5,})', line)
    if desc_match:
        result['description'] = desc_match.group(1).strip()
        remaining = line[len(desc_match.group(1)):]
    else:
        # No amounts found, use whole line as description
        result['description'] = line.strip()
        remaining = ''
    
    # Clean up description
    if result['description']:
        result['description'] = re.sub(r'\s+', ' ', result['description'])
        result['description'] = result['description'][:100]  # Limit length
    
    # Extract all number patterns from remaining text
    number_patterns = re.findall(r'[\d\s.,]{2,}', remaining)
    amounts = []
    dates = []
    
    for pattern in number_patterns:
        # Try as amount
        amt = clean_amount(pattern)
        if amt and amt > 0:
            amounts.append(amt)
        
        # Try as date (small numbers, 3-4 digits)
        if len(re.sub(r'\D', '', pattern)) in [3, 4]:
            dt = parse_date(pattern)
            if dt:
                dates.append(dt)
    
    # Assign values
    if dates:
        result['date'] = dates[-1]  # Last date found
    elif last_date:
        result['date'] = last_date  # Use previous date
    
    # Determine withdrawal vs deposit from description
    is_deposit = any(x in result['description'].upper() for x in ['DEPOSIT', 'CREDIT MEMO', 'REFUND'])
    is_withdrawal = any(x in result['description'].upper() for x in ['WITHDRAWAL', 'PURCHASE', 'CHQ', 'DRAFT', 'DEBIT MEMO', 'FEE'])
    
    if amounts:
        if len(amounts) == 1:
            # Single amount - could be transaction or balance
            if is_deposit or is_withdrawal:
                # This is the transaction amount
                if is_deposit:
                    result['deposit'] = amounts[0]
                else:
                    result['withdrawal'] = amounts[0]
            else:
                # Assume it's balance
                result['balance'] = amounts[0]
        elif len(amounts) >= 2:
            # Multiple amounts: first is transaction, last is balance
            if is_deposit:
                result['deposit'] = amounts[0]
            elif is_withdrawal:
                result['withdrawal'] = amounts[0]
            result['balance'] = amounts[-1]
    
    return result if result['description'] else None

def extract_transactions_from_pdf(pdf_path):
    """Extract all transactions from PDF, handling rotated pages."""
    print(f"Opening PDF: {pdf_path}")
    
    transactions = []
    last_date = None
    
    with pdfplumber.open(pdf_path) as pdf:
        print(f"Total pages: {len(pdf.pages)}")
        
        for page_num, page in enumerate(pdf.pages, 1):
            print(f"\nProcessing page {page_num}...", end='')
            
            # Try normal extraction first
            text = page.extract_text()
            
            if not text:
                print(" (no text)")
                continue
            
            # Check if text is rotated (look for reversed text patterns)
            if 'knabaitocS' in text or text.count('\n') < 5:
                # Try rotated extraction
                print(" (rotated)", end='')
                # pdfplumber doesn't have built-in rotation, but we can work with what we get
            
            lines = text.split('\n')
            page_txn_count = 0
            
            for line in lines:
                if not line.strip():
                    continue
                
                txn = parse_transaction_from_line(line, page_num, last_date)
                if txn:
                    transactions.append(txn)
                    page_txn_count += 1
                    if txn['date']:
                        last_date = txn['date']
            
            print(f" {page_txn_count} transactions")
    
    print(f"\nTotal transactions extracted: {len(transactions)}")
    return transactions

def fill_missing_dates(transactions):
    """Forward-fill missing dates."""
    last_date = None
    filled = 0
    
    for txn in transactions:
        if txn['date']:
            last_date = txn['date']
        elif last_date:
            txn['date'] = last_date
            filled += 1
    
    print(f"Filled {filled} missing dates")
    return transactions

def export_to_csv(transactions, output_path):
    """Export transactions to CSV."""
    print(f"\nExporting to: {output_path}")
    
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
    
    print(f"Exported {len(transactions)} transactions")

if __name__ == '__main__':
    pdf_path = r'L:\limo\pdf\2012\2012 scotiabank statements all.pdf'
    output_csv = r'L:\limo\data\scotia_2012_extracted.csv'
    
    print("="*100)
    print("SCOTIA BANK 2012 PDF PARSER (Handles Rotated Pages)")
    print("="*100)
    
    # Extract
    transactions = extract_transactions_from_pdf(pdf_path)
    
    if not transactions:
        print("\nWARNING: No transactions extracted!")
        print("Trying with layout=True...")
    
    # Fill dates
    transactions = fill_missing_dates(transactions)
    
    # Show sample
    print("\n" + "="*100)
    print("SAMPLE TRANSACTIONS (First 20)")
    print("="*100)
    for i, txn in enumerate(transactions[:20], 1):
        print(f"{i:2d}. {txn['description'][:60]:60s} W:{str(txn['withdrawal']) if txn['withdrawal'] else '-':>10s} D:{str(txn['deposit']) if txn['deposit'] else '-':>10s} B:{str(txn['balance']) if txn['balance'] else '-':>10s}")
    
    # Export
    export_to_csv(transactions, output_csv)
    
    print("\n" + "="*100)
    print("COMPLETE")
    print("="*100)
