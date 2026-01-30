#!/usr/bin/env python3
"""
Compare Scotia Bank 2012 data from three sources:
1. almsdata database (current state)
2. Nov 3 CSV full report
3. Today's 3 PDF files (manual extraction needed)

Output comprehensive JSON comparison for analysis.
"""

import psycopg2
import csv
import json
from datetime import datetime
from decimal import Decimal
import PyPDF2
import re
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def decimal_default(obj):
    """JSON serializer for Decimal objects."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, 'isoformat'):  # date objects
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def parse_amount(amount_str):
    """Parse amount string to Decimal."""
    if not amount_str or amount_str.strip() == '':
        return Decimal('0.00')
    clean = amount_str.replace(',', '').replace('$', '').strip()
    # Handle parentheses for negative amounts
    if clean.startswith('(') and clean.endswith(')'):
        clean = '-' + clean[1:-1]
    try:
        return Decimal(clean)
    except:
        return Decimal('0.00')

def extract_pdf_text(pdf_path):
    """Extract all text from PDF."""
    text = ""
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
    return text

def parse_scotia_pdf_transactions(text, pdf_name):
    """
    Parse Scotia Bank transactions from OCR'd PDF text.
    Handle multiple statement formats with headers and summary rows.
    """
    transactions = []
    lines = text.split('\n')
    
    # Track whether we're in a transaction section
    in_transaction_section = False
    current_year = 2012
    
    # Patterns to detect headers and summary rows
    header_patterns = [
        r'Date.*Description.*Withdrawals.*Deposits.*Balance',
        r'Transaction Date.*Description.*Debit.*Credit',
        r'Account Number.*Statement Period',
        r'Opening Balance',
        r'Closing Balance',
        r'Total Withdrawals',
        r'Total Deposits',
        r'Page \d+ of \d+',
    ]
    
    # Month abbreviations
    months = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
        'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12,
        'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
        'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12
    }
    
    for i, line in enumerate(lines):
        # Skip if line matches any header pattern
        is_header = any(re.search(pattern, line, re.IGNORECASE) for pattern in header_patterns)
        if is_header:
            continue
        
        # Skip empty lines
        if not line.strip():
            continue
        
        # Try multiple transaction patterns
        
        # Pattern 1: "Jan 31  DEPOSIT  100.00  6,320.00"
        # Date (month day) | Description | Amount | Balance
        pattern1 = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})\s+(.{5,70}?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$'
        match = re.search(pattern1, line, re.IGNORECASE)
        if match:
            month_str, day, description, amount, balance = match.groups()
            month = months.get(month_str, 1)
            try:
                date = datetime(current_year, month, int(day)).date()
                
                # Determine debit vs credit from description
                desc_clean = description.strip()
                debit = Decimal('0.00')
                credit = Decimal('0.00')
                
                # Common credit keywords
                if any(word in desc_clean.lower() for word in ['deposit', 'credit', 'transfer in', 'interest', 'refund']):
                    credit = parse_amount(amount)
                else:
                    debit = parse_amount(amount)
                
                transactions.append({
                    'date': date,
                    'description': desc_clean,
                    'debit': debit,
                    'credit': credit,
                    'balance': parse_amount(balance),
                    'source': pdf_name,
                    'raw_line': line.strip()
                })
            except:
                pass
        
        # Pattern 2: "01/31/2012  DEPOSIT  100.00"
        pattern2 = r'(\d{2})/(\d{2})/(\d{4})\s+(.{5,70}?)\s+([\d,]+\.\d{2})\s*$'
        match = re.search(pattern2, line)
        if match:
            month, day, year, description, amount = match.groups()
            try:
                date = datetime(int(year), int(month), int(day)).date()
                
                desc_clean = description.strip()
                debit = Decimal('0.00')
                credit = Decimal('0.00')
                
                if any(word in desc_clean.lower() for word in ['deposit', 'credit', 'transfer in', 'interest', 'refund']):
                    credit = parse_amount(amount)
                else:
                    debit = parse_amount(amount)
                
                transactions.append({
                    'date': date,
                    'description': desc_clean,
                    'debit': debit,
                    'credit': credit,
                    'balance': Decimal('0.00'),  # Balance not in this format
                    'source': pdf_name,
                    'raw_line': line.strip()
                })
            except:
                pass
        
        # Pattern 3: Lines with amounts but no clear date (continuation lines)
        # Skip these for now to avoid false positives
    
    return transactions

def get_database_data():
    """Get Scotia Bank 2012 transactions from database."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            COALESCE(debit_amount, 0) as debit,
            COALESCE(credit_amount, 0) as credit,
            COALESCE(balance, 0) as balance,
            created_at
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND transaction_date >= '2012-01-01' AND transaction_date < '2013-01-01'
        ORDER BY transaction_date, transaction_id
    """)
    
    transactions = []
    for row in cur.fetchall():
        transactions.append({
            'transaction_id': row[0],
            'date': row[1],
            'description': row[2],
            'debit': Decimal(str(row[3])),
            'credit': Decimal(str(row[4])),
            'balance': Decimal(str(row[5])),
            'created_at': row[6]
        })
    
    cur.close()
    conn.close()
    
    return transactions

def get_csv_data():
    """Get Scotia Bank 2012 transactions from Nov 3 CSV."""
    csv_file = r'l:\limo\reports\Scotia_Bank_2012_Full_Report.csv'
    
    transactions = []
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            transactions.append({
                'transaction_id': row['Transaction ID'],
                'date': datetime.strptime(row['Date'], '%Y-%m-%d').date(),
                'account': row['Account Number'],
                'description': row['Description'],
                'debit': parse_amount(row['Debit Amount']),
                'credit': parse_amount(row['Credit Amount']),
                'balance': parse_amount(row['Running Balance']),
                'created_at': row['Created At']
            })
    
    return transactions

def get_pdf_data():
    """Get Scotia Bank 2012 transactions from today's PDFs."""
    pdf_files = [
        (r"L:\limo\pdf\2012\2012 scotia bank statement 2_ocred.pdf", "scotia_statement_2"),
        (r"L:\limo\pdf\2012\2012 scotia bank statements 0_ocred.pdf", "scotia_statements_0"),
        (r"L:\limo\pdf\2012\2012 scotia bank statements 1_ocred.pdf", "scotia_statements_1")
    ]
    
    all_transactions = []
    pdf_metadata = {}
    
    for pdf_path, pdf_name in pdf_files:
        print(f"Processing {pdf_name}...")
        text = extract_pdf_text(pdf_path)
        
        # Extract metadata
        account_match = re.search(r'Account.*?(\d{10,})', text)
        period_match = re.search(r'Statement Period:?\s*([A-Za-z]+\s+\d+,?\s+\d{4})\s*to\s*([A-Za-z]+\s+\d+,?\s+\d{4})', text, re.IGNORECASE)
        opening_match = re.search(r'Opening Balance.*?([\d,]+\.\d{2})', text, re.IGNORECASE)
        closing_match = re.search(r'Closing Balance.*?([\d,]+\.\d{2})', text, re.IGNORECASE)
        
        pdf_metadata[pdf_name] = {
            'account': account_match.group(1) if account_match else None,
            'period_start': period_match.group(1) if period_match else None,
            'period_end': period_match.group(2) if period_match else None,
            'opening_balance': parse_amount(opening_match.group(1)) if opening_match else None,
            'closing_balance': parse_amount(closing_match.group(1)) if closing_match else None,
            'text_length': len(text)
        }
        
        # Parse transactions
        transactions = parse_scotia_pdf_transactions(text, pdf_name)
        all_transactions.extend(transactions)
        
        print(f"  Extracted: {len(transactions)} transactions")
    
    return all_transactions, pdf_metadata

def compare_sources(db_data, csv_data, pdf_data):
    """Compare transaction counts and totals across sources."""
    comparison = {
        'database': {
            'count': len(db_data),
            'total_debits': sum(t['debit'] for t in db_data),
            'total_credits': sum(t['credit'] for t in db_data),
            'date_range': {
                'first': min(t['date'] for t in db_data) if db_data else None,
                'last': max(t['date'] for t in db_data) if db_data else None
            },
            'monthly_breakdown': defaultdict(int)
        },
        'csv': {
            'count': len(csv_data),
            'total_debits': sum(t['debit'] for t in csv_data),
            'total_credits': sum(t['credit'] for t in csv_data),
            'date_range': {
                'first': min(t['date'] for t in csv_data) if csv_data else None,
                'last': max(t['date'] for t in csv_data) if csv_data else None
            },
            'monthly_breakdown': defaultdict(int)
        },
        'pdf': {
            'count': len(pdf_data),
            'total_debits': sum(t['debit'] for t in pdf_data),
            'total_credits': sum(t['credit'] for t in pdf_data),
            'date_range': {
                'first': min(t['date'] for t in pdf_data) if pdf_data else None,
                'last': max(t['date'] for t in pdf_data) if pdf_data else None
            },
            'monthly_breakdown': defaultdict(int)
        }
    }
    
    # Monthly breakdowns
    for t in db_data:
        month_key = f"{t['date'].year}-{t['date'].month:02d}"
        comparison['database']['monthly_breakdown'][month_key] += 1
    
    for t in csv_data:
        month_key = f"{t['date'].year}-{t['date'].month:02d}"
        comparison['csv']['monthly_breakdown'][month_key] += 1
    
    for t in pdf_data:
        month_key = f"{t['date'].year}-{t['date'].month:02d}"
        comparison['pdf']['monthly_breakdown'][month_key] += 1
    
    # Convert defaultdicts to regular dicts for JSON
    comparison['database']['monthly_breakdown'] = dict(comparison['database']['monthly_breakdown'])
    comparison['csv']['monthly_breakdown'] = dict(comparison['csv']['monthly_breakdown'])
    comparison['pdf']['monthly_breakdown'] = dict(comparison['pdf']['monthly_breakdown'])
    
    return comparison

def main():
    print("=" * 80)
    print("SCOTIA BANK 2012 - THREE-SOURCE COMPARISON")
    print("=" * 80)
    
    # Get data from all sources
    print("\n1. Fetching database data...")
    db_data = get_database_data()
    print(f"   Retrieved {len(db_data):,} transactions")
    
    print("\n2. Reading Nov 3 CSV...")
    csv_data = get_csv_data()
    print(f"   Retrieved {len(csv_data):,} transactions")
    
    print("\n3. Processing PDF files...")
    pdf_data, pdf_metadata = get_pdf_data()
    print(f"   Retrieved {len(pdf_data):,} transactions")
    
    # Compare sources
    print("\n4. Comparing sources...")
    comparison = compare_sources(db_data, csv_data, pdf_data)
    
    # Build comprehensive output
    output = {
        'generated_at': datetime.now().isoformat(),
        'summary': comparison,
        'pdf_metadata': pdf_metadata,
        'database_sample': db_data[:10],  # First 10 for inspection
        'csv_sample': csv_data[:10],
        'pdf_sample': pdf_data[:10] if pdf_data else [],
        'discrepancies': {
            'count_diff_db_csv': len(db_data) - len(csv_data),
            'count_diff_db_pdf': len(db_data) - len(pdf_data),
            'count_diff_csv_pdf': len(csv_data) - len(pdf_data),
            'debit_diff_db_csv': comparison['database']['total_debits'] - comparison['csv']['total_debits'],
            'credit_diff_db_csv': comparison['database']['total_credits'] - comparison['csv']['total_credits'],
        },
        'recommendations': []
    }
    
    # Add recommendations based on findings
    if len(csv_data) > len(db_data):
        output['recommendations'].append("CSV has more transactions than database - consider using CSV as authoritative")
    if len(pdf_data) == 0:
        output['recommendations'].append("PDF parsing failed - manual extraction required or pattern adjustments needed")
    if abs(output['discrepancies']['debit_diff_db_csv']) > 1000:
        output['recommendations'].append(f"Large debit discrepancy (${output['discrepancies']['debit_diff_db_csv']:,.2f}) between database and CSV")
    
    # Save to JSON
    output_file = 'scotia_2012_three_source_comparison.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, default=decimal_default)
    
    print(f"\n5. Saved comparison to {output_file}")
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\nDatabase:  {comparison['database']['count']:,} transactions")
    print(f"           Debits: ${comparison['database']['total_debits']:,.2f}")
    print(f"           Credits: ${comparison['database']['total_credits']:,.2f}")
    
    print(f"\nCSV:       {comparison['csv']['count']:,} transactions")
    print(f"           Debits: ${comparison['csv']['total_debits']:,.2f}")
    print(f"           Credits: ${comparison['csv']['total_credits']:,.2f}")
    
    print(f"\nPDF:       {comparison['pdf']['count']:,} transactions")
    print(f"           Debits: ${comparison['pdf']['total_debits']:,.2f}")
    print(f"           Credits: ${comparison['pdf']['total_credits']:,.2f}")
    
    print(f"\nDiscrepancies:")
    print(f"  DB vs CSV count: {output['discrepancies']['count_diff_db_csv']:+,}")
    print(f"  DB vs CSV debits: ${output['discrepancies']['debit_diff_db_csv']:+,.2f}")
    print(f"  DB vs CSV credits: ${output['discrepancies']['credit_diff_db_csv']:+,.2f}")
    
    if output['recommendations']:
        print(f"\nRecommendations:")
        for rec in output['recommendations']:
            print(f"  • {rec}")
    
    print("\n" + "=" * 80)
    print(f"Full details saved to: {output_file}")
    print("=" * 80)

if __name__ == '__main__':
    main()
