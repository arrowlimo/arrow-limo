#!/usr/bin/env python3
"""
Extract and verify Scotia Bank transactions from today's OCR'd PDF files.
Compare against database and Nov 3 CSV to determine accurate data source.
"""

import re
from datetime import datetime
from decimal import Decimal
import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file."""
    import PyPDF2
    text = ""
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
    return text

def parse_scotia_transactions(text):
    """Parse Scotia Bank statement transactions from OCR text."""
    transactions = []
    
    # Common Scotia Bank transaction patterns
    # Date format: MMM DD or MM/DD
    # Looking for: DATE DESCRIPTION DEBIT CREDIT BALANCE
    
    lines = text.split('\n')
    current_year = 2012
    
    for i, line in enumerate(lines):
        # Skip header/footer lines
        if 'Account Number' in line or 'Statement Period' in line or 'Page' in line:
            continue
        
        # Try to match transaction line patterns
        # Pattern 1: "Jan 31  DEPOSIT  1,000.00  6,320.00"
        pattern1 = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})\s+(.{10,60}?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$'
        
        # Pattern 2: "01/31  DEPOSIT  1,000.00"
        pattern2 = r'(\d{2})/(\d{2})\s+(.{10,60}?)\s+([\d,]+\.\d{2})\s*$'
        
        match = re.search(pattern1, line)
        if match:
            month_str, day, description, amount1, amount2 = match.groups()
            month = datetime.strptime(month_str, '%b').month
            date = datetime(current_year, month, int(day)).date()
            
            # Determine if amount1 is debit or credit based on description
            debit = Decimal('0.00')
            credit = Decimal('0.00')
            
            desc_lower = description.lower()
            if any(word in desc_lower for word in ['deposit', 'credit', 'transfer in', 'interest']):
                credit = Decimal(amount1.replace(',', ''))
            else:
                debit = Decimal(amount1.replace(',', ''))
            
            balance = Decimal(amount2.replace(',', ''))
            
            transactions.append({
                'date': date,
                'description': description.strip(),
                'debit': debit,
                'credit': credit,
                'balance': balance
            })
    
    return transactions

def main():
    pdf_files = [
        r"L:\limo\pdf\2012\2012 scotia bank statement 2_ocred.pdf",
        r"L:\limo\pdf\2012\2012 scotia bank statements 0_ocred.pdf",
        r"L:\limo\pdf\2012\2012 scotia bank statements 1_ocred.pdf"
    ]
    
    print("=" * 80)
    print("SCOTIA BANK 2012 - TODAY'S PDF ANALYSIS")
    print("=" * 80)
    
    all_pdf_transactions = []
    
    for pdf_file in pdf_files:
        print(f"\nProcessing: {pdf_file}")
        text = extract_text_from_pdf(pdf_file)
        
        if text:
            print(f"  Extracted {len(text):,} characters")
            
            # Try to find account number
            account_match = re.search(r'Account.*?(\d{10,})', text)
            if account_match:
                print(f"  Account: {account_match.group(1)}")
            
            # Try to find statement period
            period_match = re.search(r'Statement Period:?\s*([A-Za-z]+\s+\d+,?\s+\d{4})\s*to\s*([A-Za-z]+\s+\d+,?\s+\d{4})', text, re.IGNORECASE)
            if period_match:
                print(f"  Period: {period_match.group(1)} to {period_match.group(2)}")
            
            # Parse transactions
            transactions = parse_scotia_transactions(text)
            print(f"  Parsed {len(transactions)} transactions")
            
            if transactions:
                print(f"  Date range: {transactions[0]['date']} to {transactions[-1]['date']}")
                total_debits = sum(t['debit'] for t in transactions)
                total_credits = sum(t['credit'] for t in transactions)
                print(f"  Debits: ${total_debits:,.2f}")
                print(f"  Credits: ${total_credits:,.2f}")
                
                all_pdf_transactions.extend(transactions)
        else:
            print(f"  ⚠ No text extracted")
    
    print(f"\n" + "=" * 80)
    print(f"COMBINED PDF RESULTS:")
    print(f"  Total transactions: {len(all_pdf_transactions)}")
    
    if all_pdf_transactions:
        total_debits = sum(t['debit'] for t in all_pdf_transactions)
        total_credits = sum(t['credit'] for t in all_pdf_transactions)
        print(f"  Total debits: ${total_debits:,.2f}")
        print(f"  Total credits: ${total_credits:,.2f}")
        print(f"  Net: ${(total_credits - total_debits):,.2f}")
        
        # Show sample transactions
        print(f"\nSAMPLE TRANSACTIONS (first 10):")
        for t in all_pdf_transactions[:10]:
            print(f"  {t['date']} | {t['description'][:40]:40} | D:${t['debit']:>10,.2f} C:${t['credit']:>10,.2f} Bal:${t['balance']:>10,.2f}")
    
    # Compare against database
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT COUNT(*), SUM(COALESCE(debit_amount,0)), SUM(COALESCE(credit_amount,0))
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND transaction_date >= '2012-01-01' AND transaction_date < '2013-01-01'
    """)
    
    db_count, db_debits, db_credits = cur.fetchone()
    
    print(f"\n" + "=" * 80)
    print(f"COMPARISON WITH DATABASE:")
    print(f"  Database rows: {db_count:,}")
    print(f"  Database debits: ${float(db_debits):,.2f}")
    print(f"  Database credits: ${float(db_credits):,.2f}")
    
    if all_pdf_transactions:
        print(f"\n  PDF rows: {len(all_pdf_transactions):,}")
        print(f"  PDF debits: ${total_debits:,.2f}")
        print(f"  PDF credits: ${total_credits:,.2f}")
        
        row_diff = abs(len(all_pdf_transactions) - db_count)
        debit_diff = abs(total_debits - Decimal(str(db_debits)))
        credit_diff = abs(total_credits - Decimal(str(db_credits)))
        
        print(f"\n  Difference:")
        print(f"    Rows: {row_diff:,}")
        print(f"    Debits: ${debit_diff:,.2f}")
        print(f"    Credits: ${credit_diff:,.2f}")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 80)
    print("NOTE: If PDF parsing is incomplete, we'll need to manually verify")
    print("      the statement pages or use the Nov 3 CSV as authoritative source.")
    print("=" * 80)

if __name__ == '__main__':
    main()
