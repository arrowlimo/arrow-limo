#!/usr/bin/env python3
"""
Parse 2012 CIBC banking PDF statements and compare with database records.

The PDFs contain transactions in format:
Date Description Withdrawals ($) Deposits ($) Balance ($)
Jan 3 PURCHASE000001198103 63.50 7,113.84
"""

import pdfplumber
import re
from datetime import datetime
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor
import os

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def parse_month_day(text, year=2012):
    """Parse 'Jan 3' format to date."""
    month_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    
    match = re.match(r'([a-z]{3})\s*(\d{1,2})', text.lower())
    if match:
        month_str, day_str = match.groups()
        month = month_map.get(month_str)
        if month:
            try:
                return datetime(year, month, int(day_str)).date()
            except:
                pass
    return None

def clean_amount(text):
    """Convert text to Decimal amount."""
    if not text or text.strip() in ['', '-', 'V', 'c']:
        return None
    
    # Remove non-numeric characters except decimal point and minus
    text = re.sub(r'[^\d.-]', '', text.strip())
    
    try:
        return Decimal(text)
    except:
        return None

def extract_transactions_from_pdf(pdf_path):
    """Extract transaction data from OCR'd CIBC statement PDF."""
    transactions = []
    
    print(f"\n📄 Analyzing: {os.path.basename(pdf_path)}")
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"   Pages: {len(pdf.pages)}")
            
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if not text:
                    continue
                
                lines = text.split('\n')
                current_date = None
                
                for line in lines:
                    # Skip header/footer lines
                    if any(skip in line for skip in ['Account Statement', 'Transaction details', 
                                                      'Page ', 'Withdrawals ($)', 'Balance forward',
                                                      'Opening balance', 'Closing balance']):
                        continue
                    
                    # Check for date at start of line (e.g., "Jan 3")
                    date_match = re.match(r'^([A-Z][a-z]{2}\s+\d{1,2})\s+(.+)$', line)
                    if date_match:
                        date_str, rest = date_match.groups()
                        trans_date = parse_month_day(date_str)
                        
                        if trans_date and trans_date.year == 2012:
                            current_date = trans_date
                            
                            # Parse the rest of the line
                            # Format: Description Withdrawal Deposit Balance
                            # Need to find last 3 numbers (withdrawal, deposit, balance)
                            
                            # Extract all numbers from the line
                            numbers = re.findall(r'[\d,]+\.\d{2}', rest)
                            
                            if numbers:
                                # Get description (everything before numbers)
                                desc_match = re.match(r'(.+?)\s*[\d,]+\.\d{2}', rest)
                                description = desc_match.group(1).strip() if desc_match else rest.split()[0]
                                
                                # Last 3 numbers are: withdrawal, deposit, balance (or withdrawal, balance if no deposit)
                                amounts = [clean_amount(n) for n in numbers]
                                amounts = [a for a in amounts if a is not None]
                                
                                if len(amounts) >= 2:
                                    # Could be: [withdrawal, balance] or [deposit, balance] or [withdrawal, deposit, balance]
                                    if len(amounts) == 2:
                                        # Check if description suggests deposit
                                        if any(kw in description.upper() for kw in ['DEPOSIT', 'CREDIT MEMO', 'E-TRANSFER RECLAIM', 'MISC PAYMENT']):
                                            debit = None
                                            credit = amounts[0]
                                            balance = amounts[1]
                                        else:
                                            debit = amounts[0]
                                            credit = None
                                            balance = amounts[1]
                                    elif len(amounts) == 3:
                                        debit = amounts[0] if amounts[0] > 0 else None
                                        credit = amounts[1] if amounts[1] > 0 else None
                                        balance = amounts[2]
                                    else:
                                        continue
                                    
                                    transactions.append({
                                        'date': current_date,
                                        'description': description,
                                        'debit': debit,
                                        'credit': credit,
                                        'balance': balance,
                                        'source_pdf': os.path.basename(pdf_path),
                                        'page': page_num
                                    })
                    
                    # Handle continuation lines (same date continues)
                    elif current_date and re.match(r'^[A-Z\s]+', line) and not line.startswith(' '):
                        # Might be a continuation
                        numbers = re.findall(r'[\d,]+\.\d{2}', line)
                        if numbers:
                            desc_match = re.match(r'(.+?)\s*[\d,]+\.\d{2}', line)
                            description = desc_match.group(1).strip() if desc_match else line.split()[0]
                            
                            amounts = [clean_amount(n) for n in numbers]
                            amounts = [a for a in amounts if a is not None]
                            
                            if len(amounts) >= 2:
                                if len(amounts) == 2:
                                    if any(kw in description.upper() for kw in ['DEPOSIT', 'CREDIT MEMO', 'E-TRANSFER RECLAIM', 'MISC PAYMENT']):
                                        debit = None
                                        credit = amounts[0]
                                        balance = amounts[1]
                                    else:
                                        debit = amounts[0]
                                        credit = None
                                        balance = amounts[1]
                                elif len(amounts) == 3:
                                    debit = amounts[0] if amounts[0] > 0 else None
                                    credit = amounts[1] if amounts[1] > 0 else None
                                    balance = amounts[2]
                                else:
                                    continue
                                
                                transactions.append({
                                    'date': current_date,
                                    'description': description,
                                    'debit': debit,
                                    'credit': credit,
                                    'balance': balance,
                                    'source_pdf': os.path.basename(pdf_path),
                                    'page': page_num
                                })
    
    except Exception as e:
        print(f"   [WARN]  Error reading PDF: {e}")
        import traceback
        traceback.print_exc()
        return []
    
    return transactions

def main():
    pdf_files = [
        r"L:\limo\CIBC UPLOADS\2012cibc banking jan-mar_ocred.pdf",
        r"L:\limo\CIBC UPLOADS\2012cibc banking apr- may_ocred.pdf",
        r"L:\limo\CIBC UPLOADS\2012cibc banking jun-dec_ocred.pdf",
    ]
    
    all_pdf_transactions = []
    
    for pdf_file in pdf_files:
        if not os.path.exists(pdf_file):
            print(f"[WARN]  File not found: {pdf_file}")
            continue
        
        transactions = extract_transactions_from_pdf(pdf_file)
        all_pdf_transactions.extend(transactions)
        
        if transactions:
            print(f"   ✓ Extracted {len(transactions)} transactions")
            # Show samples
            for sample in transactions[:3]:
                debit_str = f"${sample['debit']:.2f}" if sample['debit'] else "-"
                credit_str = f"${sample['credit']:.2f}" if sample['credit'] else "-"
                print(f"   {sample['date']} | {sample['description'][:40]:<40} | D: {debit_str:>10} | C: {credit_str:>10}")
    
    if not all_pdf_transactions:
        print("\n[FAIL] No transactions extracted from PDFs")
        return
    
    # Sort by date
    all_pdf_transactions.sort(key=lambda x: x['date'])
    
    # Summary
    print(f"\n{'='*80}")
    print(f"📊 PDF EXTRACTION SUMMARY")
    print(f"{'='*80}")
    print(f"Total transactions extracted: {len(all_pdf_transactions)}")
    
    if all_pdf_transactions:
        print(f"Date range: {all_pdf_transactions[0]['date']} to {all_pdf_transactions[-1]['date']}")
        
        total_debits = sum(t['debit'] for t in all_pdf_transactions if t['debit'])
        total_credits = sum(t['credit'] for t in all_pdf_transactions if t['credit'])
        debit_count = sum(1 for t in all_pdf_transactions if t['debit'])
        credit_count = sum(1 for t in all_pdf_transactions if t['credit'])
        
        print(f"Debit transactions: {debit_count} (${total_debits:,.2f})")
        print(f"Credit transactions: {credit_count} (${total_credits:,.2f})")
        print(f"Net: ${total_credits - total_debits:,.2f}")
    
    # Compare with database
    print(f"\n{'='*80}")
    print(f"🔍 COMPARISON WITH DATABASE")
    print(f"{'='*80}")
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get existing 2012 banking data
    cur.execute("""
        SELECT 
            COUNT(*) as count,
            MIN(transaction_date) as min_date,
            MAX(transaction_date) as max_date,
            SUM(debit_amount) as total_debits,
            SUM(credit_amount) as total_credits
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    """)
    db_summary = cur.fetchone()
    
    print(f"Database 2012 transactions: {db_summary['count']}")
    print(f"Database date range: {db_summary['min_date']} to {db_summary['max_date']}")
    print(f"Database total debits: ${db_summary['total_debits'] or 0:,.2f}")
    print(f"Database total credits: ${db_summary['total_credits'] or 0:,.2f}")
    
    # Difference analysis
    pdf_total = len(all_pdf_transactions)
    db_total = db_summary['count']
    
    print(f"\n📈 COVERAGE ANALYSIS")
    print(f"PDF transactions: {pdf_total}")
    print(f"Database transactions: {db_total}")
    
    if pdf_total > db_total:
        print(f"[WARN]  PDF has {pdf_total - db_total} MORE transactions than database!")
    elif db_total > pdf_total:
        print(f"✓ Database has {db_total - pdf_total} MORE transactions than PDF")
    else:
        print(f"✓ Transaction counts match!")
    
    # Check for matches (sample)
    print(f"\n{'='*80}")
    print(f"🔗 MATCHING ANALYSIS (sampling 100 transactions)")
    print(f"{'='*80}")
    
    matches = 0
    mismatches = []
    
    for pdf_trans in all_pdf_transactions[::max(1, len(all_pdf_transactions)//100)][:100]:
        # Check if exists in database (by date and amount)
        debit_check = pdf_trans['debit'] or Decimal('0')
        credit_check = pdf_trans['credit'] or Decimal('0')
        
        cur.execute("""
            SELECT transaction_id, description, debit_amount, credit_amount
            FROM banking_transactions
            WHERE transaction_date = %s
            AND (
                (debit_amount IS NOT NULL AND debit_amount BETWEEN %s - 0.02 AND %s + 0.02)
                OR (credit_amount IS NOT NULL AND credit_amount BETWEEN %s - 0.02 AND %s + 0.02)
            )
            LIMIT 1
        """, (pdf_trans['date'], debit_check, debit_check, credit_check, credit_check))
        
        db_match = cur.fetchone()
        if db_match:
            matches += 1
        else:
            mismatches.append(pdf_trans)
    
    print(f"Exact matches (date + amount ±$0.02): {matches}/100 sampled ({matches}%)")
    
    if mismatches:
        print(f"\n📋 SAMPLE UNMATCHED PDF TRANSACTIONS (first 10):")
        for trans in mismatches[:10]:
            debit_str = f"${trans['debit']:.2f}" if trans['debit'] else "-"
            credit_str = f"${trans['credit']:.2f}" if trans['credit'] else "-"
            print(f"{trans['date']} | {trans['description'][:50]:<50} | D: {debit_str:>10} | C: {credit_str:>10}")
    
    cur.close()
    conn.close()
    
    print(f"\n[OK] Analysis complete!")

if __name__ == '__main__':
    main()
