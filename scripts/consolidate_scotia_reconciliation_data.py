"""
Consolidate all unique transactions from Scotia Bank reconciliation PDFs.

This script:
1. Parses all 12 PDF reconciliation files
2. Deduplicates transactions using date+vendor+amount key
3. Exports consolidated unique transactions to CSV
4. Provides summary statistics and comparison to database

Created: November 24, 2025
"""

import os
import re
import csv
import psycopg2
from datetime import datetime
from decimal import Decimal
from collections import defaultdict, Counter
import PyPDF2

# Database connection parameters
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

# PDF files to process (corrected paths from working parse script)
pdf_files = [
    ('QB Recon 4', r'L:\limo\pdf\2012\2012 scotiabank bank reconciliation detailed 4.pdf'),
    ('QB Recon 5', r'L:\limo\pdf\2012\2012 scotiabank bank reconciliation detailed 5.pdf'),
    ('QB Recon 6', r'L:\limo\pdf\2012\2012 scotiabank bank reconciliation detailed 6.pdf'),
    ('QB Recon 7', r'L:\limo\pdf\2012\2012 scotiabank bank reconciliation detailed 7.pdf'),
    ('QB Recon 8', r'L:\limo\pdf\2012\2012 scotiabank bank reconciliation detailed 8.pdf'),
    ('QB Recon 9', r'L:\limo\pdf\2012\2012 scotiabank bank reconciliation detailed 9.pdf'),
    ('Statement 2', r'L:\limo\pdf\2012\2012 scotia bank statement 2_ocred.pdf'),
    ('Statement 0', r'L:\limo\pdf\2012\2012 scotia bank statements 0_ocred.pdf'),
    ('Statement 1', r'L:\limo\pdf\2012\2012 scotia bank statements 1_ocred.pdf'),
    ('QB Recon 3', r'L:\limo\pdf\2012\2012 quickbooks scotiabank bank reconciliation detailed 3.pdf'),
    ('Document', r'L:\limo\pdf\2012\Document_20251124_0001.pdf'),
    ('CIBC Jan', r'L:\limo\pdf\2012\jan reconsile cibc 2012.pdf'),
]

def extract_pdf_text(pdf_path):
    """Extract text from PDF file."""
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text()
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
    return text

def parse_reconciliation_transactions(text, source_name):
    """
    Parse QuickBooks reconciliation report format.
    
    Format: Type Date Num Name Cir Amount Balance
    Example: Cheque 01/03/2012 4506 Centex X -63.50 7,113.84
    """
    transactions = []
    
    # Pattern for reconciliation report lines (including General Journal entries and OCR variants)
    # Handle OCR errors: Pm! → Pmt, Prnt → Pmt, Chequs/Cheqye/Gheque → Cheque
    pattern = re.compile(
        r'^(Cheque|Chequs|Cheqye|Gheque|Deposit|Bill\s*Pm[t!]|Bill\s*Prnt|General\s*[Jj]ournal)\s*(?:-?\s*Cheq[uq]?[uq]?e)?\s+'  # Type with OCR variants
        r'(\d{2}/\d{2}/\d{4})\s+'                     # Date
        r'([\w/]+|-?\d+|dd|w/d|wld|WD|DD|Online)?\s*' # Num (optional)
        r'(.+?)\s+'                                    # Name/vendor
        r'(X|-|C)?\s*'                                 # Cleared status
        r'(-?[\d,]+\.\d{2})\s+'                       # Amount
        r'(-?[\d,]+\.\d{2})\s*$',                     # Balance
        re.MULTILINE
    )
    
    for match in pattern.finditer(text):
        txn_type = match.group(1)
        date_str = match.group(2)
        num = match.group(3) or ''
        vendor = match.group(4).strip()
        cleared = match.group(5) or '-'
        amount_str = match.group(6).replace(',', '')
        balance_str = match.group(7).replace(',', '')
        
        try:
            txn_date = datetime.strptime(date_str, '%m/%d/%Y').date()
            amount = Decimal(amount_str)
            balance = Decimal(balance_str)
            
            # Normalize transaction type (handle OCR errors)
            txn_type = txn_type.strip()
            if txn_type.lower() in ['chequs', 'cheqye', 'gheque']:
                txn_type = 'Cheque'
            elif 'pm' in txn_type.lower() or 'prnt' in txn_type.lower():
                txn_type = 'Bill Pmt'
            elif txn_type.lower() == 'general journal':
                txn_type = 'General Journal'
            
            # Flag General Journal entries for journal table routing
            is_journal = txn_type == 'General Journal'
            
            transactions.append({
                'source_file': source_name,
                'type': txn_type,
                'date': txn_date,
                'num': num,
                'vendor': vendor,
                'cleared': cleared,
                'amount': amount,
                'balance': balance,
                'is_journal_entry': is_journal,
                'target_table': 'journal' if is_journal else 'banking_transactions'
            })
        except (ValueError, Exception) as e:
            continue
    
    return transactions

def get_unique_key(txn):
    """Generate unique key for transaction deduplication."""
    return f"{txn['date']}|{txn['vendor']}|{txn['amount']}"

def consolidate_transactions():
    """
    Parse all PDFs and consolidate unique transactions.
    """
    print("=" * 80)
    print("SCOTIA BANK RECONCILIATION DATA CONSOLIDATION")
    print("=" * 80)
    print()
    
    # Parse all files
    all_transactions = []
    file_stats = {}
    
    print("1. Parsing PDF files...")
    for name, path in pdf_files:
        if not os.path.exists(path):
            print(f"   {name}: FILE NOT FOUND")
            continue
        
        text = extract_pdf_text(path)
        transactions = parse_reconciliation_transactions(text, name)
        all_transactions.extend(transactions)
        file_stats[name] = len(transactions)
        print(f"   {name}: {len(transactions)} transactions")
    
    print(f"\n   TOTAL: {len(all_transactions)} transactions")
    print()
    
    # Deduplicate transactions
    print("2. Deduplicating transactions...")
    unique_transactions = {}
    duplicate_count = 0
    source_tracking = defaultdict(list)  # Track which files contributed each unique transaction
    
    for txn in all_transactions:
        key = get_unique_key(txn)
        if key not in unique_transactions:
            unique_transactions[key] = txn
            source_tracking[key].append(txn['source_file'])
        else:
            duplicate_count += 1
            source_tracking[key].append(txn['source_file'])
    
    unique_list = sorted(unique_transactions.values(), key=lambda x: x['date'])
    
    print(f"   Total transactions: {len(all_transactions)}")
    print(f"   Unique transactions: {len(unique_list)}")
    print(f"   Duplicates removed: {duplicate_count}")
    print()
    
    # Analyze by year
    print("3. Analyzing by year...")
    year_stats = defaultdict(lambda: {'count': 0, 'debits': Decimal('0'), 'credits': Decimal('0')})
    
    for txn in unique_list:
        year = txn['date'].year
        year_stats[year]['count'] += 1
        if txn['amount'] < 0:
            year_stats[year]['debits'] += abs(txn['amount'])
        else:
            year_stats[year]['credits'] += txn['amount']
    
    for year in sorted(year_stats.keys()):
        stats = year_stats[year]
        print(f"   {year}: {stats['count']} transactions, "
              f"Debits: ${stats['debits']:,.2f}, Credits: ${stats['credits']:,.2f}")
    print()
    
    # Compare to database
    print("4. Comparing to database...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cur = conn.cursor()
        
        # Get Scotia Bank transactions from database
        cur.execute("""
            SELECT 
                COUNT(*) as count,
                SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END) as debits,
                SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END) as credits
            FROM banking_transactions
            WHERE account_number = '903990106011'
        """)
        
        db_stats = cur.fetchone()
        db_count = db_stats[0] or 0
        db_debits = db_stats[1] or Decimal('0')
        db_credits = db_stats[2] or Decimal('0')
        
        # Calculate totals from year_stats
        total_debits = sum(stats['debits'] for stats in year_stats.values())
        total_credits = sum(stats['credits'] for stats in year_stats.values())
        
        print(f"   Database: {db_count} transactions")
        print(f"   Database Debits: ${db_debits:,.2f}")
        print(f"   Database Credits: ${db_credits:,.2f}")
        print()
        print(f"   Consolidated PDF: {len(unique_list)} transactions")
        print(f"   Consolidated Debits: ${total_debits:,.2f}")
        print(f"   Consolidated Credits: ${total_credits:,.2f}")
        print()
        print(f"   Difference: {len(unique_list) - db_count} transactions missing from database")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"   Error connecting to database: {e}")
    print()
    
    # Export to CSV
    print("5. Exporting to CSV...")
    output_file = r'L:\limo\data\scotia_consolidated_all_years.csv'
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['date', 'type', 'num', 'vendor', 'cleared', 'amount', 'balance', 
                      'source_files', 'appears_in_count']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for txn in unique_list:
            key = get_unique_key(txn)
            sources = source_tracking[key]
            
            writer.writerow({
                'date': txn['date'].strftime('%Y-%m-%d'),
                'type': txn['type'],
                'num': txn['num'],
                'vendor': txn['vendor'],
                'cleared': txn['cleared'],
                'amount': float(txn['amount']),
                'balance': float(txn['balance']),
                'source_files': '; '.join(set(sources)),
                'appears_in_count': len(sources)
            })
    
    print(f"   Exported to: {output_file}")
    print(f"   Total rows: {len(unique_list)}")
    print()
    
    # Show transactions that appeared in multiple files
    print("6. Multi-source transactions analysis...")
    multi_source = [(key, sources) for key, sources in source_tracking.items() if len(sources) > 1]
    multi_source_count = len(multi_source)
    
    print(f"   Transactions appearing in multiple files: {multi_source_count}")
    
    if multi_source_count > 0:
        # Count by number of sources
        source_counts = Counter(len(sources) for _, sources in multi_source)
        for count in sorted(source_counts.keys(), reverse=True):
            print(f"   - In {count} files: {source_counts[count]} transactions")
    
    print()
    
    # Show most common cross-file patterns
    if multi_source_count > 0:
        print("7. Most common file combinations...")
        file_combos = Counter(tuple(sorted(set(sources))) for _, sources in multi_source)
        
        for combo, count in file_combos.most_common(10):
            print(f"   {count} transactions in: {', '.join(combo)}")
    
    print()
    print("=" * 80)
    print("CONSOLIDATION COMPLETE")
    print("=" * 80)
    
    return unique_list

if __name__ == '__main__':
    consolidate_transactions()
