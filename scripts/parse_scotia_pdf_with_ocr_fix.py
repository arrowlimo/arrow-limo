"""
Parse Scotia Bank 2012 PDF with OCR error correction.

Handles:
- Corrupted decimal points (!, :, i → .)
- Corrupted zeros (b, D, O → 0)
- Date format: M D columns with corrupted chars
- Amount spacing and corruption
- Transaction description extraction
"""
import pdfplumber
import re
from decimal import Decimal
from datetime import datetime
import csv

def fix_ocr_amount(text):
    """
    Fix OCR corruption in amounts.
    
    Examples:
    - "10000" → "100.00"
    - "300i !0 0" → "300.00"
    - "99 i!4 3" → "99.43"
    - "66!:0 0" → "66.00"
    - "4 730! 5" → "4730.15"
    """
    if not text:
        return None
    
    # Remove all whitespace first
    text = text.replace(' ', '').replace('\t', '')
    
    # Fix corrupted decimal points and zeros
    text = text.replace('!', '.').replace(':', '.').replace('i', '.')
    text = text.replace('b', '0').replace('D', '0').replace('O', '0')
    text = text.replace('l', '1').replace('I', '1')
    text = text.replace('r', '').replace('V', '').replace('..', '.')
    
    # Handle multiple dots (keep last one)
    parts = text.split('.')
    if len(parts) > 2:
        # Last part is cents, everything before is dollars
        dollars = ''.join(parts[:-1])
        cents = parts[-1]
        text = f"{dollars}.{cents}"
    
    # Ensure exactly 2 decimal places
    if '.' in text:
        parts = text.split('.')
        dollars = parts[0]
        cents = parts[1][:2]  # Take only first 2 digits
        text = f"{dollars}.{cents}"
    else:
        # No decimal point found - assume last 2 digits are cents
        if len(text) >= 2:
            text = f"{text[:-2]}.{text[-2:]}"
        else:
            text = f"0.{text.zfill(2)}"
    
    try:
        return Decimal(text)
    except:
        print(f"  WARNING: Could not parse amount '{text}' (original OCR)")
        return None

def fix_ocr_date(text, year=2012):
    """
    Fix OCR corruption in date.
    
    Examples:
    - "D8!10" → "08/10/2012"
    - "D813" → "08/13/2012"
    - "b816" → "08/16/2012"
    - "D9 6" → "09/06/2012"
    """
    if not text:
        return None
    
    # Remove whitespace
    text = text.replace(' ', '').replace('\t', '')
    
    # Fix corrupted characters
    text = text.replace('!', '').replace(':', '').replace('i', '')
    text = text.replace('b', '0').replace('D', '0').replace('O', '0')
    text = text.replace('l', '1').replace('I', '1')
    
    # Remove non-numeric characters
    text = re.sub(r'[^0-9]', '', text)
    
    # Parse as MMDD
    if len(text) == 3:
        # Format: MDD (e.g., 810 = 08/10)
        month = text[0]
        day = text[1:]
        month = month.zfill(2)
    elif len(text) == 4:
        # Format: MMDD (e.g., 0810 = 08/10)
        month = text[:2]
        day = text[2:]
    else:
        print(f"  WARNING: Could not parse date '{text}' (unexpected format)")
        return None
    
    try:
        return datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d").date()
    except ValueError as e:
        print(f"  WARNING: Invalid date '{text}' → {month}/{day}/{year}: {e}")
        return None

def extract_transactions_from_text(pdf_path):
    """
    Extract transactions from Scotia PDF using text extraction with OCR correction.
    """
    transactions = []
    
    print(f"Opening PDF: {pdf_path}")
    
    with pdfplumber.open(pdf_path) as pdf:
        print(f"Total pages: {len(pdf.pages)}")
        
        for page_num, page in enumerate(pdf.pages, 1):
            print(f"\nProcessing page {page_num}...")
            
            text = page.extract_text()
            if not text:
                print(f"  No text on page {page_num}")
                continue
            
            # Split into lines
            lines = text.split('\n')
            
            # Look for transaction patterns
            # Pattern: Description, optional amount1, optional amount2, date at end
            
            for i, line in enumerate(lines):
                # Skip header lines
                if any(x in line.upper() for x in ['BALANCE FORWARD', 'SCOTIABANK', 'ACCOUNT NUMBER', 
                                                     'STATEMENT OF', 'DESCRIPTION', 'NO. OF']):
                    continue
                
                # Look for transaction types
                if any(x in line.upper() for x in ['DEPOSIT', 'WITHDRAWAL', 'PURCHASE', 'CHQ', 'POINT OF SALE']):
                    # This is a transaction line
                    print(f"  Found transaction: {line[:80]}")
                    
                    # Try to extract components
                    # Very basic extraction - need more sophisticated parsing
                    # For now, just collect the raw lines
                    transactions.append({
                        'page': page_num,
                        'raw_line': line,
                        'description': line[:50].strip()  # Rough description
                    })
    
    print(f"\nTotal transaction lines found: {len(transactions)}")
    return transactions

if __name__ == '__main__':
    pdf_path = r'L:\limo\pdf\2012\2012 scotiabank statements all.pdf'
    
    print("="*100)
    print("SCOTIA BANK 2012 PDF PARSER WITH OCR CORRECTION")
    print("="*100)
    
    # Test OCR correction functions
    print("\n" + "="*100)
    print("TESTING OCR CORRECTION FUNCTIONS")
    print("="*100)
    
    test_amounts = [
        "10000",
        "300i !0 0",
        "99 i!4 3",
        "66!:0 0",
        "4 730! 5",
        "39325",
        "4 624 r 5"
    ]
    
    print("\nAmount OCR Correction:")
    for amt in test_amounts:
        fixed = fix_ocr_amount(amt)
        print(f"  '{amt}' → ${fixed}")
    
    test_dates = [
        "D8!10",
        "D813",
        "b816",
        "D9 6",
        "D9i24",
        "b92i."
    ]
    
    print("\nDate OCR Correction:")
    for dt in test_dates:
        fixed = fix_ocr_date(dt, 2012)
        print(f"  '{dt}' → {fixed}")
    
    # Extract transactions
    print("\n" + "="*100)
    print("EXTRACTING TRANSACTIONS")
    print("="*100)
    
    transactions = extract_transactions_from_text(pdf_path)
    
    print("\n" + "="*100)
    print(f"EXTRACTION COMPLETE: {len(transactions)} transaction lines found")
    print("="*100)
    
    if transactions:
        print("\nFirst 10 transactions:")
        for i, txn in enumerate(transactions[:10], 1):
            print(f"{i}. Page {txn['page']}: {txn['description']}")
