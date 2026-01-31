#!/usr/bin/env python3
"""
Analyze 2012 CIBC banking PDF statements (OCR'd) and compare with database records.

Extracts transaction data from PDF bank statements and analyzes:
- Transaction count and date coverage
- Total debits/credits
- Comparison with existing banking_transactions table
- Identifies missing or duplicate entries
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

def parse_date(date_str):
    """Parse various date formats from bank statements."""
    date_str = date_str.strip()
    
    # Try common formats
    patterns = [
        r'(\d{4})[/-](\d{2})[/-](\d{2})',  # YYYY-MM-DD or YYYY/MM/DD
        r'(\d{2})[/-](\d{2})[/-](\d{4})',  # MM-DD-YYYY or DD-MM-YYYY
        r'(\d{2})[/-](\d{2})[/-](\d{2})',  # MM-DD-YY or DD-MM-YY
        r'(\w{3})\s+(\d{1,2})\s+(\d{4})',  # Jan 15 2012
    ]
    
    for pattern in patterns:
        match = re.search(pattern, date_str)
        if match:
            try:
                # Try different interpretations
                groups = match.groups()
                if len(groups[0]) == 4:  # YYYY-MM-DD
                    return datetime(int(groups[0]), int(groups[1]), int(groups[2])).date()
                elif len(groups) == 3 and groups[0].isalpha():  # Jan 15 2012
                    month_map = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                                'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}
                    month = month_map.get(groups[0][:3].lower())
                    if month:
                        return datetime(int(groups[2]), month, int(groups[1])).date()
                else:
                    # Try MM-DD-YYYY
                    try:
                        return datetime(int(groups[2] if len(groups[2]) == 4 else f"20{groups[2]}"), 
                                      int(groups[0]), int(groups[1])).date()
                    except:
                        # Try DD-MM-YYYY
                        return datetime(int(groups[2] if len(groups[2]) == 4 else f"20{groups[2]}"), 
                                      int(groups[1]), int(groups[0])).date()
            except:
                continue
    return None

def parse_amount(amount_str):
    """Parse dollar amounts from various formats."""
    if not amount_str:
        return None
    
    # Remove currency symbols, commas, spaces
    amount_str = amount_str.replace('$', '').replace(',', '').replace(' ', '').strip()
    
    # Handle brackets for negative amounts
    if amount_str.startswith('(') and amount_str.endswith(')'):
        amount_str = '-' + amount_str[1:-1]
    
    try:
        return Decimal(amount_str)
    except:
        return None

def extract_transactions_from_pdf(pdf_path):
    """Extract transaction data from OCR'd PDF bank statement."""
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
                
                for line in lines:
                    # Skip header/footer lines
                    if any(skip in line.lower() for skip in ['statement', 'page', 'account', 'balance', 'cibc', 'banking']):
                        continue
                    
                    # Look for transaction patterns
                    # Common formats:
                    # DATE  DESCRIPTION  DEBIT  CREDIT  BALANCE
                    # 2012-01-15  POS PURCHASE  45.67    1234.56
                    
                    # Try to find date pattern
                    date_match = re.search(r'\b(20\d{2}[/-]\d{2}[/-]\d{2}|\d{2}[/-]\d{2}[/-]20\d{2}|[A-Z][a-z]{2}\s+\d{1,2}\s+20\d{2})\b', line)
                    if not date_match:
                        continue
                    
                    trans_date = parse_date(date_match.group(1))
                    if not trans_date or trans_date.year != 2012:
                        continue
                    
                    # Extract description and amounts
                    # Look for amounts (format: 1,234.56 or 1234.56)
                    amount_matches = re.findall(r'\$?\s*[\d,]+\.\d{2}', line)
                    
                    if len(amount_matches) >= 1:
                        # Get description (text between date and first amount)
                        desc_match = re.search(rf'{re.escape(date_match.group(1))}(.+?){re.escape(amount_matches[0])}', line)
                        description = desc_match.group(1).strip() if desc_match else line[date_match.end():].strip()
                        
                        # Parse amounts
                        amounts = [parse_amount(amt) for amt in amount_matches]
                        amounts = [amt for amt in amounts if amt is not None]
                        
                        if amounts:
                            # Determine debit/credit
                            # Usually: debit, credit, balance
                            debit = amounts[0] if len(amounts) >= 1 else None
                            credit = amounts[1] if len(amounts) >= 2 else None
                            balance = amounts[2] if len(amounts) >= 3 else None
                            
                            # Clean up description
                            description = re.sub(r'\s+', ' ', description).strip()
                            
                            transactions.append({
                                'date': trans_date,
                                'description': description,
                                'debit': debit if debit and debit > 0 else None,
                                'credit': credit if credit and credit > 0 else None,
                                'balance': balance,
                                'source_pdf': os.path.basename(pdf_path),
                                'page': page_num
                            })
    
    except Exception as e:
        print(f"   [WARN]  Error reading PDF: {e}")
        return []
    
    return transactions

def analyze_pdf_transactions(pdf_files):
    """Analyze all PDF statements and compare with database."""
    
    all_pdf_transactions = []
    
    for pdf_file in pdf_files:
        if not os.path.exists(pdf_file):
            print(f"[WARN]  File not found: {pdf_file}")
            continue
        
        transactions = extract_transactions_from_pdf(pdf_file)
        all_pdf_transactions.extend(transactions)
        
        if transactions:
            print(f"   ✓ Extracted {len(transactions)} potential transactions")
            # Show sample
            if transactions:
                sample = transactions[0]
                print(f"   Sample: {sample['date']} | {sample['description'][:50]} | "
                      f"Debit: ${sample['debit'] or 0:.2f} | Credit: ${sample['credit'] or 0:.2f}")
    
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
        print(f"Total debits: ${total_debits:,.2f}")
        print(f"Total credits: ${total_credits:,.2f}")
    
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
    
    # Check for matches
    print(f"\n{'='*80}")
    print(f"🔗 MATCHING ANALYSIS")
    print(f"{'='*80}")
    
    matches = 0
    near_matches = 0
    
    for pdf_trans in all_pdf_transactions[:100]:  # Sample first 100
        # Check if exists in database (by date and amount)
        debit_check = pdf_trans['debit'] or Decimal('0')
        credit_check = pdf_trans['credit'] or Decimal('0')
        
        cur.execute("""
            SELECT transaction_id, description, debit_amount, credit_amount
            FROM banking_transactions
            WHERE transaction_date = %s
            AND (
                (debit_amount BETWEEN %s - 0.02 AND %s + 0.02)
                OR (credit_amount BETWEEN %s - 0.02 AND %s + 0.02)
            )
            LIMIT 1
        """, (pdf_trans['date'], debit_check, debit_check, credit_check, credit_check))
        
        db_match = cur.fetchone()
        if db_match:
            matches += 1
        else:
            # Check for near matches (same date, different amount)
            cur.execute("""
                SELECT COUNT(*) as count
                FROM banking_transactions
                WHERE transaction_date = %s
            """, (pdf_trans['date'],))
            if cur.fetchone()['count'] > 0:
                near_matches += 1
    
    print(f"Exact matches (date + amount): {matches}/100 sampled")
    print(f"Near matches (same date): {near_matches}/100 sampled")
    
    # Show unmatched transactions
    print(f"\n{'='*80}")
    print(f"📋 SAMPLE UNMATCHED PDF TRANSACTIONS")
    print(f"{'='*80}")
    
    unmatched_count = 0
    for pdf_trans in all_pdf_transactions[:20]:
        debit_check = pdf_trans['debit'] or Decimal('0')
        credit_check = pdf_trans['credit'] or Decimal('0')
        
        cur.execute("""
            SELECT transaction_id
            FROM banking_transactions
            WHERE transaction_date = %s
            AND (
                (debit_amount BETWEEN %s - 0.02 AND %s + 0.02)
                OR (credit_amount BETWEEN %s - 0.02 AND %s + 0.02)
            )
        """, (pdf_trans['date'], debit_check, debit_check, credit_check, credit_check))
        
        if not cur.fetchone():
            unmatched_count += 1
            print(f"{pdf_trans['date']} | {pdf_trans['description'][:60]:<60} | "
                  f"D: ${pdf_trans['debit'] or 0:>8.2f} | C: ${pdf_trans['credit'] or 0:>8.2f}")
            if unmatched_count >= 10:
                break
    
    cur.close()
    conn.close()
    
    print(f"\n[OK] Analysis complete!")

if __name__ == '__main__':
    pdf_files = [
        r"L:\limo\CIBC UPLOADS\2012cibc banking jan-mar_ocred.pdf",
        r"L:\limo\CIBC UPLOADS\2012cibc banking apr- may_ocred.pdf",
        r"L:\limo\CIBC UPLOADS\2012cibc banking jun-dec_ocred.pdf",
    ]
    
    analyze_pdf_transactions(pdf_files)
