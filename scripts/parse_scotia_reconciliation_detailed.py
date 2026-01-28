#!/usr/bin/env python3
"""
Parse Scotia Bank 2012 detailed reconciliation PDFs (QuickBooks format).

This handles QuickBooks reconciliation reports with structure:
- Type Date Num Name Cir Amount Balance
- Cleared/Uncleared sections
- Running balance calculations
"""

import sys
import os
import psycopg2
import csv
import json
import PyPDF2
import re
from decimal import Decimal
from datetime import datetime
from collections import defaultdict

# Database connection
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'database': os.environ.get('DB_NAME', 'almsdata'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', '***REMOVED***')
}

def extract_pdf_text(pdf_path):
    """Extract text from PDF file."""
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
    except Exception as e:
        print(f"Error extracting PDF text: {e}")
        return ""

def parse_reconciliation_transactions(text):
    """
    Parse QuickBooks reconciliation format transactions.
    
    Format: Type Date Num Name Cir Amount Balance
    Example: Cheque 07/03/2012 dd Chase Paymentech X -480.47 -480.47
    """
    transactions = []
    lines = text.split('\n')
    
    # Pattern for transaction lines
    # Type Date Num Name Cir Amount Balance
    # Handle OCR errors: Pm! → Pmt, Prnt → Pmt, Chequs/Cheqye/Gheque → Cheque
    pattern = re.compile(
        r'^(Cheque|Chequs|Cheqye|Gheque|Deposit|Bill\s*Pm[t!]|Bill\s*Prnt|General\s*[Jj]ournal)\s*(?:-?\s*Cheq[uq]?[uq]?e)?\s+'  # Type with OCR variants
        r'(\d{2}/\d{2}/\d{4})\s+'                   # Date
        r'([\w/]+|-?\d+|dd|w/d|wld|WD|DD|Online)?\s*'  # Num (optional)
        r'(.+?)\s+'                                 # Name (vendor)
        r'(X|-|C)?\s*'                             # Cir (cleared marker, optional)
        r'(-?[\d,]+\.\d{2})\s+'                    # Amount
        r'(-?[\d,]+\.\d{2})\s*$',                  # Balance
        re.MULTILINE
    )
    
    for line in lines:
        # Skip headers, summaries, and section markers
        if any(skip in line for skip in [
            'Type Date Num',
            'Beginning Balance',
            'Total Cheques',
            'Total Deposits',
            'Total Cleared',
            'Cleared Balance',
            'Register Balance',
            'Uncleared Transactions',
            'New Transactions',
            'Page ',
            '===',
            'Cleared Transactions',
            'items'
        ]):
            continue
        
        match = pattern.match(line.strip())
        if match:
            trans_type, date_str, num, vendor, cleared, amount_str, balance_str = match.groups()
            
            # Normalize transaction type (handle OCR errors)
            trans_type = trans_type.strip()
            if trans_type.lower() in ['chequs', 'cheqye', 'gheque']:
                trans_type = 'Cheque'
            elif 'pm' in trans_type.lower() or 'prnt' in trans_type.lower():
                trans_type = 'Bill Pmt'
            elif trans_type.lower() == 'general journal':
                trans_type = 'General Journal'
            
            # Parse date
            try:
                trans_date = datetime.strptime(date_str, '%m/%d/%Y').date()
            except:
                continue
            
            # Parse amount (remove commas)
            amount = Decimal(amount_str.replace(',', ''))
            
            # Determine if debit or credit
            if amount < 0:
                debit = abs(amount)
                credit = Decimal('0.00')
            else:
                debit = Decimal('0.00')
                credit = amount
            
            # Clean vendor name
            vendor = vendor.strip()
            # Remove trailing ellipsis
            vendor = re.sub(r'\s*\.\.\.\s*$', '', vendor)
            
            # Determine target table based on transaction type
            is_journal_entry = trans_type.lower() == 'general journal'
            
            transactions.append({
                'date': trans_date,
                'type': trans_type,
                'num': num or '',
                'vendor': vendor,
                'cleared': cleared == 'X',
                'debit': debit,
                'credit': credit,
                'amount': amount,
                'balance': Decimal(balance_str.replace(',', '')),
                'description': f"{trans_type} - {vendor}",
                'is_journal_entry': is_journal_entry,  # Flag for routing to journal table vs banking
                'target_table': 'journal' if is_journal_entry else 'banking_transactions'
            })
    
    return transactions

def get_database_data():
    """Fetch Scotia 2012 transactions from database."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT transaction_date, description, debit_amount, credit_amount, balance
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        ORDER BY transaction_date, transaction_id
    """)
    
    transactions = []
    for row in cur.fetchall():
        transactions.append({
            'date': row[0],
            'description': row[1],
            'debit': row[2] or Decimal('0.00'),
            'credit': row[3] or Decimal('0.00'),
            'balance': row[4] or Decimal('0.00')
        })
    
    cur.close()
    conn.close()
    return transactions

def get_csv_data():
    """Read Nov 3 CSV data."""
    csv_path = r'L:\limo\reports\Scotia_Bank_2012_Full_Report.csv'
    transactions = []
    
    if not os.path.exists(csv_path):
        print(f"CSV file not found: {csv_path}")
        return transactions
    
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                date = datetime.strptime(row['Date'], '%Y-%m-%d').date()
                debit = Decimal(row['Debit Amount']) if row['Debit Amount'] and float(row['Debit Amount']) > 0 else Decimal('0.00')
                credit = Decimal(row['Credit Amount']) if row['Credit Amount'] and float(row['Credit Amount']) > 0 else Decimal('0.00')
                
                transactions.append({
                    'date': date,
                    'description': row['Description'],
                    'debit': debit,
                    'credit': credit,
                    'balance': Decimal(row['Running Balance'])
                })
            except Exception as e:
                continue
    
    return transactions

def compare_sources(db_data, csv_data, pdf_data):
    """Compare all three sources."""
    comparison = {
        'database': {
            'count': len(db_data),
            'total_debits': sum(t['debit'] for t in db_data),
            'total_credits': sum(t['credit'] for t in db_data),
            'date_range': f"{min(t['date'] for t in db_data)} to {max(t['date'] for t in db_data)}" if db_data else "N/A"
        },
        'csv': {
            'count': len(csv_data),
            'total_debits': sum(t['debit'] for t in csv_data),
            'total_credits': sum(t['credit'] for t in csv_data),
            'date_range': f"{min(t['date'] for t in csv_data)} to {max(t['date'] for t in csv_data)}" if csv_data else "N/A"
        },
        'pdf_reconciliation': {
            'count': len(pdf_data),
            'total_debits': sum(t['debit'] for t in pdf_data),
            'total_credits': sum(t['credit'] for t in pdf_data),
            'date_range': f"{min(t['date'] for t in pdf_data)} to {max(t['date'] for t in pdf_data)}" if pdf_data else "N/A",
            'cleared_count': sum(1 for t in pdf_data if t.get('cleared', False))
        }
    }
    
    # Monthly breakdowns
    for source_name, data in [('database', db_data), ('csv', csv_data), ('pdf_reconciliation', pdf_data)]:
        monthly = defaultdict(lambda: {'count': 0, 'debits': Decimal('0.00'), 'credits': Decimal('0.00')})
        for t in data:
            month_key = f"{t['date'].year}-{t['date'].month:02d}"
            monthly[month_key]['count'] += 1
            monthly[month_key]['debits'] += t['debit']
            monthly[month_key]['credits'] += t['credit']
        
        comparison[source_name]['monthly'] = dict(monthly)
    
    return comparison

def decimal_default(obj):
    """JSON serializer for Decimal and date objects."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, type(datetime.now().date()))):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def main():
    print("Scotia Bank 2012 Reconciliation Analysis")
    print("=" * 80)
    
    # Parse all reconciliation PDFs
    pdf_files = [
        r'L:\limo\pdf\2012\2012 scotiabank bank reconciliation detailed 4.pdf',
        r'L:\limo\pdf\2012\2012 scotiabank bank reconciliation detailed 5.pdf',
        r'L:\limo\pdf\2012\2012 scotiabank bank reconciliation detailed 6.pdf',
        r'L:\limo\pdf\2012\2012 scotiabank bank reconciliation detailed 7.pdf',
        r'L:\limo\pdf\2012\2012 scotiabank bank reconciliation detailed 8.pdf',
        r'L:\limo\pdf\2012\2012 scotiabank bank reconciliation detailed 9.pdf',
        r'L:\limo\pdf\2012\2012 scotia bank statement 2_ocred.pdf',
        r'L:\limo\pdf\2012\2012 scotia bank statements 0_ocred.pdf',
        r'L:\limo\pdf\2012\2012 scotia bank statements 1_ocred.pdf',
        r'L:\limo\pdf\2012\2012 quickbooks scotiabank bank reconciliation detailed 3.pdf',
        r'L:\limo\pdf\2012\Document_20251124_0001.pdf',
        r'L:\limo\pdf\2012\jan reconsile cibc 2012.pdf'
    ]
    
    all_pdf_transactions = []
    print(f"\n1. Parsing {len(pdf_files)} reconciliation PDFs...")
    
    for pdf_path in pdf_files:
        if not os.path.exists(pdf_path):
            print(f"   SKIP: {os.path.basename(pdf_path)} not found")
            continue
            
        print(f"   Processing: {os.path.basename(pdf_path)}")
        pdf_text = extract_pdf_text(pdf_path)
        transactions = parse_reconciliation_transactions(pdf_text)
        print(f"      Extracted: {len(transactions)} transactions")
        all_pdf_transactions.extend(transactions)
    
    pdf_transactions = all_pdf_transactions
    print(f"\n   TOTAL EXTRACTED: {len(pdf_transactions)} transactions")
    
    if pdf_transactions:
        print(f"   Date range: {min(t['date'] for t in pdf_transactions)} to {max(t['date'] for t in pdf_transactions)}")
        cleared = sum(1 for t in pdf_transactions if t.get('cleared', False))
        print(f"   Cleared: {cleared}, Uncleared: {len(pdf_transactions) - cleared}")
    
    # Get database data
    print("\n2. Fetching database data...")
    db_transactions = get_database_data()
    print(f"   Retrieved: {len(db_transactions)} transactions")
    
    # Get CSV data
    print("\n3. Reading Nov 3 CSV...")
    csv_transactions = get_csv_data()
    print(f"   Retrieved: {len(csv_transactions)} transactions")
    
    # Compare sources
    print("\n4. Comparing sources...")
    comparison = compare_sources(db_transactions, csv_transactions, pdf_transactions)
    
    # Save to JSON
    output = {
        'generated_at': datetime.now().isoformat(),
        'summary': comparison,
        'pdf_reconciliation_samples': pdf_transactions[:20] if pdf_transactions else [],
        'database_samples': db_transactions[:10],
        'csv_samples': csv_transactions[:10],
        'discrepancies': {
            'db_vs_csv_count': len(db_transactions) - len(csv_transactions),
            'db_vs_csv_debits': float(comparison['database']['total_debits'] - comparison['csv']['total_debits']),
            'db_vs_csv_credits': float(comparison['database']['total_credits'] - comparison['csv']['total_credits']),
            'db_vs_pdf_count': len(db_transactions) - len(pdf_transactions),
            'csv_vs_pdf_count': len(csv_transactions) - len(pdf_transactions)
        }
    }
    
    output_path = 'scotia_2012_reconciliation_comparison.json'
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, default=decimal_default)
    
    print(f"\n5. Saved comparison to {output_path}")
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\nDatabase:  {comparison['database']['count']} transactions")
    print(f"           Debits: ${comparison['database']['total_debits']:,.2f}")
    print(f"           Credits: ${comparison['database']['total_credits']:,.2f}")
    
    print(f"\nCSV:       {comparison['csv']['count']} transactions")
    print(f"           Debits: ${comparison['csv']['total_debits']:,.2f}")
    print(f"           Credits: ${comparison['csv']['total_credits']:,.2f}")
    
    print(f"\nPDF Reconciliation: {comparison['pdf_reconciliation']['count']} transactions")
    print(f"           Debits: ${comparison['pdf_reconciliation']['total_debits']:,.2f}")
    print(f"           Credits: ${comparison['pdf_reconciliation']['total_credits']:,.2f}")
    print(f"           Cleared: {comparison['pdf_reconciliation']['cleared_count']}")
    
    print(f"\nDiscrepancies:")
    print(f"  DB vs CSV count: {output['discrepancies']['db_vs_csv_count']:+d}")
    print(f"  DB vs CSV debits: ${output['discrepancies']['db_vs_csv_debits']:+,.2f}")
    print(f"  DB vs CSV credits: ${output['discrepancies']['db_vs_csv_credits']:+,.2f}")
    print(f"  DB vs PDF count: {output['discrepancies']['db_vs_pdf_count']:+d}")
    print(f"  CSV vs PDF count: {output['discrepancies']['csv_vs_pdf_count']:+d}")
    
    print("\n" + "=" * 80)
    print(f"Full details saved to: {output_path}")
    print("=" * 80)

if __name__ == '__main__':
    main()
