#!/usr/bin/env python
"""
Scan CIBC QuickBooks reconciliation PDFs and match to almsdata tables.
Extracts transaction data from reconciliation reports and compares with database.
"""

import psycopg2
import os
import re
from pathlib import Path
from datetime import datetime
from decimal import Decimal

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def find_reconciliation_pdfs():
    """Find all reconciliation PDF files"""
    search_paths = [
        r'L:\limo\pdf',
        r'L:\limo\pdf\2012',
        r'L:\limo\quickbooks',
        r'L:\limo\banking',
        r'L:\limo\reports',
    ]
    
    pdf_files = []
    patterns = [
        '*reconcil*.pdf',
        '*recon*.pdf',
        '*cibc*.pdf',
        '*bank*.pdf',
        '*statement*.pdf',
    ]
    
    for search_path in search_paths:
        if os.path.exists(search_path):
            for pattern in patterns:
                path_obj = Path(search_path)
                pdf_files.extend(path_obj.glob(pattern))
                # Recursive search
                pdf_files.extend(path_obj.glob(f'**/{pattern}'))
    
    # Remove duplicates
    pdf_files = list(set(pdf_files))
    return sorted(pdf_files)

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF using available tools"""
    try:
        # Try pdfplumber first (if available)
        import pdfplumber
        text_content = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_content.append(text)
        return '\n'.join(text_content)
    except ImportError:
        pass
    
    try:
        # Try PyPDF2 as fallback
        import PyPDF2
        text_content = []
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    text_content.append(text)
        return '\n'.join(text_content)
    except ImportError:
        pass
    
    # If no PDF libraries available, suggest OCR approach
    return None

def parse_reconciliation_data(text):
    """Parse transaction data from reconciliation report text"""
    transactions = []
    
    # Common patterns in QuickBooks reconciliation reports
    # Date | Description | Debit | Credit | Balance
    
    # Pattern: MM/DD/YYYY or DD/MM/YYYY followed by description and amounts
    line_pattern = re.compile(
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(.+?)\s+([\d,]+\.?\d{0,2})\s*([\d,]+\.?\d{0,2})?\s*([\d,]+\.?\d{0,2})?',
        re.MULTILINE
    )
    
    for match in line_pattern.finditer(text):
        date_str = match.group(1)
        description = match.group(2).strip()
        amount1 = match.group(3).replace(',', '')
        amount2 = match.group(4).replace(',', '') if match.group(4) else None
        amount3 = match.group(5).replace(',', '') if match.group(5) else None
        
        # Try to parse date
        try:
            # Try various date formats
            for fmt in ['%m/%d/%Y', '%d/%m/%Y', '%m-%d-%Y', '%d-%m-%Y', '%m/%d/%y', '%d/%m/%y']:
                try:
                    txn_date = datetime.strptime(date_str, fmt).date()
                    break
                except ValueError:
                    continue
            else:
                continue  # Skip if no format matched
            
            # Determine debit/credit amounts
            debit = None
            credit = None
            balance = None
            
            if amount3:
                # Three amounts: debit, credit, balance
                debit = Decimal(amount1) if amount1 != '0.00' else None
                credit = Decimal(amount2) if amount2 and amount2 != '0.00' else None
                balance = Decimal(amount3)
            elif amount2:
                # Two amounts: could be debit/credit or amount/balance
                if 'DEPOSIT' in description.upper() or 'CREDIT' in description.upper():
                    credit = Decimal(amount1)
                    balance = Decimal(amount2)
                else:
                    debit = Decimal(amount1)
                    balance = Decimal(amount2)
            else:
                # Single amount - assume debit
                debit = Decimal(amount1)
            
            transactions.append({
                'date': txn_date,
                'description': description,
                'debit': debit,
                'credit': credit,
                'balance': balance
            })
            
        except Exception as e:
            continue  # Skip malformed lines
    
    return transactions

def match_to_banking_transactions(txn, cur):
    """Match parsed transaction to banking_transactions table"""
    # Try exact match on date and amount
    if txn['debit']:
        cur.execute("""
            SELECT transaction_id, description, debit_amount, balance
            FROM banking_transactions
            WHERE transaction_date = %s
            AND ABS(debit_amount - %s) < 0.01
            AND account_number = '0228362'
        """, (txn['date'], txn['debit']))
    elif txn['credit']:
        cur.execute("""
            SELECT transaction_id, description, credit_amount, balance
            FROM banking_transactions
            WHERE transaction_date = %s
            AND ABS(credit_amount - %s) < 0.01
            AND account_number = '0228362'
        """, (txn['date'], txn['credit']))
    else:
        return None
    
    matches = cur.fetchall()
    return matches

def main():
    print("=== CIBC QUICKBOOKS RECONCILIATION PDF SCANNER ===\n")
    
    # Step 1: Find reconciliation PDFs
    print("Step 1: Finding reconciliation PDF files...")
    pdf_files = find_reconciliation_pdfs()
    
    if not pdf_files:
        print("[FAIL] No reconciliation PDF files found")
        print("\nSearched in:")
        print("  - L:\\limo\\pdf")
        print("  - L:\\limo\\pdf\\2012")
        print("  - L:\\limo\\quickbooks")
        print("  - L:\\limo\\banking")
        print("  - L:\\limo\\reports")
        return
    
    print(f"Found {len(pdf_files)} PDF file(s):\n")
    for i, pdf_file in enumerate(pdf_files, 1):
        size_mb = pdf_file.stat().st_size / (1024 * 1024)
        print(f"  {i}. {pdf_file.name} ({size_mb:.2f} MB)")
        print(f"     Path: {pdf_file}")
    
    # Step 2: Check for PDF processing libraries
    print("\n" + "="*80)
    print("Step 2: Checking PDF processing capabilities...")
    
    has_pdfplumber = False
    has_pypdf2 = False
    
    try:
        import pdfplumber
        has_pdfplumber = True
        print("[OK] pdfplumber available")
    except ImportError:
        print("[WARN]  pdfplumber not installed")
    
    try:
        import PyPDF2
        has_pypdf2 = True
        print("[OK] PyPDF2 available")
    except ImportError:
        print("[WARN]  PyPDF2 not installed")
    
    if not has_pdfplumber and not has_pypdf2:
        print("\n[FAIL] No PDF processing libraries available")
        print("\nTo install:")
        print("  pip install pdfplumber")
        print("  - OR -")
        print("  pip install PyPDF2")
        return
    
    # Step 3: Process each PDF
    print("\n" + "="*80)
    print("Step 3: Processing PDF files...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    for pdf_file in pdf_files:
        print(f"\n{'='*80}")
        print(f"Processing: {pdf_file.name}")
        print(f"{'='*80}")
        
        # Extract text
        print("Extracting text...")
        text = extract_text_from_pdf(pdf_file)
        
        if not text:
            print("[FAIL] Could not extract text from PDF")
            continue
        
        print(f"[OK] Extracted {len(text)} characters")
        
        # Parse transactions
        print("Parsing transactions...")
        transactions = parse_reconciliation_data(text)
        
        if not transactions:
            print("[WARN]  No transactions found in expected format")
            print("   PDF may require manual review or OCR")
            
            # Show sample text for debugging
            print("\nSample text (first 500 chars):")
            print(text[:500])
            continue
        
        print(f"[OK] Found {len(transactions)} transaction(s)")
        
        # Match to database
        print("\nMatching to banking_transactions...")
        matched_count = 0
        unmatched_count = 0
        
        for txn in transactions[:20]:  # Show first 20 for now
            matches = match_to_banking_transactions(txn, cur)
            
            if matches:
                matched_count += 1
                print(f"  [OK] {txn['date']} | {txn['description'][:40]:40} | ${(txn['debit'] or txn['credit']):.2f}")
            else:
                unmatched_count += 1
                print(f"  [FAIL] {txn['date']} | {txn['description'][:40]:40} | ${(txn['debit'] or txn['credit']):.2f}")
        
        if len(transactions) > 20:
            print(f"\n  ... and {len(transactions) - 20} more transactions")
        
        print(f"\nMatched: {matched_count}")
        print(f"Unmatched: {unmatched_count}")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total PDFs processed: {len(pdf_files)}")
    print("\nNext steps:")
    print("1. Review unmatched transactions")
    print("2. Check for missing entries in banking_transactions")
    print("3. Verify reconciliation completeness")

if __name__ == '__main__':
    main()
