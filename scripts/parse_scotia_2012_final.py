"""
Scotia Bank 2012 PDF Parser - Final Version
Works with OCR artifacts and extracts all transactions.
"""
import pdfplumber
import re
from decimal import Decimal
from datetime import datetime
import csv
import hashlib

def clean_amount(text):
    """Clean OCR artifacts from amounts - improved for bank statement format."""
    if not text:
        return None
    
    original = str(text).strip()
    
    # First pass: identify likely decimal point position
    # Bank statements format: "1 234 56" means $1,234.56
    # Last 2 digits (or last group of 2) are usually cents
    
    # Replace OCR artifacts
    text = original.replace('!', '').replace(':', '').replace('i', '')
    text = text.replace('l', '1').replace('I', '1').replace('|', '1')
    text = text.replace('O', '0').replace('o', '0').replace('D', '0').replace('b', '0')
    text = text.replace(',', '').replace("'", '').replace('"', '').replace('Q', '0')
    text = text.replace('j', '').replace('°', '0')
    
    # Keep spaces temporarily to identify groups
    parts = text.split()
    
    if len(parts) >= 2:
        # Multiple number groups - last group is likely cents
        # e.g., "20 000" → $200.00, "1 234 56" → $1,234.56
        last_part = re.sub(r'[^0-9]', '', parts[-1])
        other_parts = ' '.join(parts[:-1])
        other_parts = re.sub(r'[^0-9]', '', other_parts)
        
        if len(last_part) == 2:
            # Last part is 2 digits = cents
            text = f"{other_parts}.{last_part}"
        elif len(last_part) == 1:
            # Last part is 1 digit = cents
            text = f"{other_parts}.0{last_part}"
        else:
            # Last part is more digits - treat as dollars, assume 00 cents
            text = f"{other_parts}{last_part}.00"
    else:
        # Single group of digits
        text = re.sub(r'[^0-9.]', '', text)
    
    # Remove any remaining non-numeric except decimal
    text = re.sub(r'[^0-9.]', '', text)
    
    if not text or text == '.':
        return None
    
    # Handle multiple decimal points
    if text.count('.') > 1:
        parts = text.split('.')
        text = ''.join(parts[:-1]) + '.' + parts[-1]
    
    # Ensure proper decimal format
    if '.' in text:
        parts = text.split('.')
        dollars = parts[0] if parts[0] else '0'
        cents = parts[1][:2] if len(parts) > 1 and parts[1] else '00'
        text = f"{dollars}.{cents.ljust(2, '0')}"
    else:
        # No decimal found - assume last 2 digits are cents
        if len(text) >= 3:
            text = f"{text[:-2]}.{text[-2:]}"
        elif len(text) == 2:
            text = f"0.{text}"
        elif len(text) == 1:
            text = f"0.0{text}"
    
    try:
        val = Decimal(text)
        # Sanity check: bank transactions rarely exceed $100,000
        if val > 100000:
            return None
        return val if val > 0 else None
    except:
        return None

def parse_date_mmdd(text, year=2012):
    """Parse date from MM/DD or M/D format."""
    if not text:
        return None
    
    # Clean text
    text = str(text).strip()
    text = re.sub(r'[^0-9/]', '', text)
    
    # Try MM/DD format
    match = re.search(r'(\d{1,2})/(\d{1,2})', text)
    if match:
        month, day = match.groups()
        try:
            return datetime.strptime(f"{year}-{month.zfill(2)}-{day.zfill(2)}", "%Y-%m-%d").date()
        except:
            pass
    
    # Try MMDD or MDD format (no slash)
    nums = re.findall(r'\d+', text)
    if nums:
        numstr = ''.join(nums)
        if len(numstr) == 3:  # MDD
            month = numstr[0]
            day = numstr[1:]
        elif len(numstr) == 4:  # MMDD
            month = numstr[:2]
            day = numstr[2:]
        else:
            return None
        
        try:
            return datetime.strptime(f"{year}-{month.zfill(2)}-{day.zfill(2)}", "%Y-%m-%d").date()
        except:
            return None
    
    return None

def extract_transactions_from_pdf(pdf_path):
    """Extract all transactions from Scotia PDF."""
    print(f"Opening: {pdf_path}")
    
    transactions = []
    last_date = None
    last_balance = None
    
    with pdfplumber.open(pdf_path) as pdf:
        print(f"Pages: {len(pdf.pages)}\n")
        
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if not text:
                continue
            
            lines = text.split('\n')
            page_txns = 0
            
            for line_num, line in enumerate(lines):
                line = line.strip()
                if not line or len(line) < 10:
                    continue
                
                # Skip headers and footers
                if any(skip in line.upper() for skip in [
                    'SCOTIABANK', 'ACCOUNT NUMBER', 'STATEMENT OF', 'RED DEER', 
                    'ARROW LIMOUSINE', 'NO. OF', 'TOTAL AMOUNT', 'DEBITS', 'CREDITS',
                    'ENCLOSURES', 'PAGE', 'CLASS MAIL'
                ]):
                    continue
                
                # Look for transaction keywords
                is_txn = False
                txn_type = None
                
                if 'BALANCE FORWARD' in line.upper():
                    is_txn = True
                    txn_type = 'BALANCE FORWARD'
                elif 'DEPOSIT' in line.upper():
                    is_txn = True
                    txn_type = 'DEPOSIT'
                elif 'WITHDRAWAL' in line.upper() or 'ABM' in line.upper():
                    is_txn = True
                    txn_type = 'WITHDRAWAL'
                elif 'PURCHASE' in line.upper():
                    is_txn = True
                    txn_type = 'PURCHASE'
                elif re.search(r'CHQ\s+\d+', line, re.IGNORECASE):
                    is_txn = True
                    txn_type = 'CHQ'
                elif 'DRAFT' in line.upper():
                    is_txn = True
                    txn_type = 'DRAFT'
                elif 'REFUND' in line.upper():
                    is_txn = True
                    txn_type = 'REFUND'
                elif 'MEMO' in line.upper():
                    is_txn = True
                    txn_type = 'MEMO'
                elif 'FEE' in line.upper() or 'CHARGE' in line.upper():
                    is_txn = True
                    txn_type = 'FEE'
                
                if not is_txn:
                    continue
                
                # Extract description (first 60 chars, cleaned)
                desc = line[:80].strip()
                desc = re.sub(r'\s+', ' ', desc)
                
                # Extract all number groups from line
                number_groups = re.findall(r'[\d!:iblIDO°oFfjCcVvrp.,\s]{2,}', line)
                
                # Parse each number group
                amounts = []
                dates = []
                
                for ng in number_groups:
                    # Try as amount
                    amt = clean_amount(ng)
                    if amt:
                        amounts.append(amt)
                    
                    # Try as date (shorter numbers)
                    cleaned = re.sub(r'[^0-9]', '', ng)
                    if len(cleaned) in [3, 4]:
                        dt = parse_date_mmdd(ng)
                        if dt:
                            dates.append(dt)
                
                # Determine withdrawal vs deposit
                is_deposit = txn_type in ['DEPOSIT', 'REFUND', 'CREDIT']
                is_withdrawal = txn_type in ['WITHDRAWAL', 'PURCHASE', 'CHQ', 'DRAFT', 'FEE', 'CHARGE']
                
                # Assign amounts
                withdrawal = None
                deposit = None
                balance = None
                date = None
                
                if dates:
                    date = dates[-1]
                    last_date = date
                elif last_date:
                    date = last_date
                
                if amounts:
                    if len(amounts) == 1:
                        # Single amount - could be transaction or balance
                        if txn_type == 'BALANCE FORWARD':
                            balance = amounts[0]
                            last_balance = balance
                        elif is_deposit:
                            deposit = amounts[0]
                        elif is_withdrawal:
                            withdrawal = amounts[0]
                        else:
                            balance = amounts[0]
                    elif len(amounts) >= 2:
                        # Multiple amounts: first is transaction, last is balance
                        if is_deposit:
                            deposit = amounts[0]
                        elif is_withdrawal:
                            withdrawal = amounts[0]
                        balance = amounts[-1]
                        last_balance = balance
                
                # Create transaction record
                txn = {
                    'page': page_num,
                    'line': line_num + 1,
                    'date': date,
                    'description': desc[:100],
                    'withdrawal': withdrawal,
                    'deposit': deposit,
                    'balance': balance,
                    'raw_line': line[:150]
                }
                
                transactions.append(txn)
                page_txns += 1
            
            if page_txns > 0:
                print(f"Page {page_num:2d}: {page_txns:3d} transactions")
    
    print(f"\nTotal: {len(transactions)} transactions extracted")
    return transactions

def export_to_csv(transactions, output_path):
    """Export to CSV for database import."""
    print(f"\nExporting to: {output_path}")
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['page', 'line', 'date', 'description', 'withdrawal', 'deposit', 'balance'])
        
        for txn in transactions:
            writer.writerow([
                txn['page'],
                txn['line'],
                txn['date'].strftime('%Y-%m-%d') if txn['date'] else '',
                txn['description'],
                f"{txn['withdrawal']:.2f}" if txn['withdrawal'] else '',
                f"{txn['deposit']:.2f}" if txn['deposit'] else '',
                f"{txn['balance']:.2f}" if txn['balance'] else ''
            ])
    
    print(f"Exported {len(transactions)} transactions")

if __name__ == '__main__':
    pdf_path = r'L:\limo\pdf\2012\2012 scotiabank statements all.pdf'
    output_csv = r'L:\limo\data\scotia_2012_final_extraction.csv'
    
    print("="*80)
    print("SCOTIA BANK 2012 TRANSACTION EXTRACTION")
    print("="*80)
    print()
    
    transactions = extract_transactions_from_pdf(pdf_path)
    
    if transactions:
        print("\n" + "="*80)
        print("SAMPLE (First 30 transactions)")
        print("="*80)
        print(f"{'Pg':>3} {'Date':>10} {'Description':45} {'Withdraw':>10} {'Deposit':>10} {'Balance':>10}")
        print("-"*80)
        
        for txn in transactions[:30]:
            print(f"{txn['page']:3d} {str(txn['date'])[:10] if txn['date'] else '':10s} "
                  f"{txn['description'][:45]:45s} "
                  f"{str(txn['withdrawal'])[:10] if txn['withdrawal'] else '':>10s} "
                  f"{str(txn['deposit'])[:10] if txn['deposit'] else '':>10s} "
                  f"{str(txn['balance'])[:10] if txn['balance'] else '':>10s}")
        
        export_to_csv(transactions, output_csv)
        
        print("\n" + "="*80)
        print("EXTRACTION COMPLETE")
        print("="*80)
        print(f"\nNext steps:")
        print(f"1. Review {output_csv}")
        print(f"2. Import to database: banking_transactions table")
        print(f"3. Verify running balances")
    else:
        print("\nERROR: No transactions extracted!")
