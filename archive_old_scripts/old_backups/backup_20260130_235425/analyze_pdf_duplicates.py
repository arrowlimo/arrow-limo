#!/usr/bin/env python3
"""
Analyze all 12 PDF files for duplicate transactions.
"""

import os
import sys
import psycopg2
from decimal import Decimal
from datetime import datetime
from collections import defaultdict, Counter
import PyPDF2
import re

# Database connection
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'database': os.environ.get('DB_NAME', 'almsdata'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', '***REDACTED***')
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
        return ""

def parse_reconciliation_transactions(text):
    """Parse QuickBooks reconciliation format transactions."""
    transactions = []
    lines = text.split('\n')
    
    pattern = re.compile(
        r'^(Cheque|Deposit|Bill Pmt|Bill Pm!)\s+'
        r'(\d{2}/\d{2}/\d{4})\s+'
        r'([\w/]+|-?\d+|dd|w/d|wld|WD|DD|Online)?\s*'
        r'(.+?)\s+'
        r'(X|-|C)?\s*'
        r'(-?[\d,]+\.\d{2})\s+'
        r'(-?[\d,]+\.\d{2})\s*$',
        re.MULTILINE
    )
    
    for line in lines:
        if any(skip in line for skip in [
            'Type Date Num', 'Beginning Balance', 'Total Cheques',
            'Total Deposits', 'Total Cleared', 'Cleared Balance',
            'Register Balance', 'Uncleared Transactions', 'New Transactions',
            'Page ', '===', 'Cleared Transactions', 'items'
        ]):
            continue
        
        match = pattern.match(line.strip())
        if match:
            trans_type, date_str, num, vendor, cleared, amount_str, balance_str = match.groups()
            
            try:
                trans_date = datetime.strptime(date_str, '%m/%d/%Y').date()
            except:
                continue
            
            amount = Decimal(amount_str.replace(',', ''))
            
            if amount < 0:
                debit = abs(amount)
                credit = Decimal('0.00')
            else:
                debit = Decimal('0.00')
                credit = amount
            
            vendor = vendor.strip()
            vendor = re.sub(r'\s*\.\.\.\s*$', '', vendor)
            
            transactions.append({
                'date': trans_date,
                'type': trans_type,
                'num': num or '',
                'vendor': vendor,
                'cleared': cleared == 'X',
                'debit': debit,
                'credit': credit,
                'amount': amount,
                'description': f"{trans_type} - {vendor}"
            })
    
    return transactions

def main():
    print("Duplicate Transaction Analysis - 12 PDF Files")
    print("=" * 80)
    
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
        ('CIBC Jan', r'L:\limo\pdf\2012\jan reconsile cibc 2012.pdf')
    ]
    
    all_transactions = []
    file_transactions = {}
    
    print("\n1. Parsing all PDF files...")
    for name, pdf_path in pdf_files:
        if not os.path.exists(pdf_path):
            print(f"   {name}: NOT FOUND")
            continue
        
        text = extract_pdf_text(pdf_path)
        transactions = parse_reconciliation_transactions(text)
        file_transactions[name] = transactions
        
        for txn in transactions:
            txn['source_file'] = name
            all_transactions.append(txn)
        
        print(f"   {name}: {len(transactions)} transactions")
    
    total = len(all_transactions)
    print(f"\n   TOTAL: {total} transactions across all files")
    
    # Analyze duplicates
    print("\n2. Analyzing for duplicates...")
    
    # Key 1: Exact match (date + vendor + amount)
    exact_key = lambda t: f"{t['date']}|{t['vendor']}|{t['amount']}"
    exact_groups = defaultdict(list)
    for txn in all_transactions:
        exact_groups[exact_key(txn)].append(txn)
    
    exact_dupes = {k: v for k, v in exact_groups.items() if len(v) > 1}
    
    # Key 2: Date + amount only
    date_amt_key = lambda t: f"{t['date']}|{t['amount']}"
    date_amt_groups = defaultdict(list)
    for txn in all_transactions:
        date_amt_groups[date_amt_key(txn)].append(txn)
    
    date_amt_dupes = {k: v for k, v in date_amt_groups.items() if len(v) > 1}
    
    # Key 3: Cross-file duplicates
    cross_file_dupes = {}
    for k, txns in exact_groups.items():
        if len(txns) > 1:
            files = set(t['source_file'] for t in txns)
            if len(files) > 1:
                cross_file_dupes[k] = txns
    
    print("\n" + "=" * 80)
    print("DUPLICATE ANALYSIS RESULTS")
    print("=" * 80)
    
    print(f"\nTotal transactions: {total}")
    print(f"Unique transactions (date+vendor+amount): {len(exact_groups)}")
    print(f"Duplicate groups: {len(exact_dupes)}")
    
    if exact_dupes:
        total_dupe_count = sum(len(v) for v in exact_dupes.values())
        unique_dupe_count = len(exact_dupes)
        print(f"  Total duplicate transactions: {total_dupe_count}")
        print(f"  Net duplicates to remove: {total_dupe_count - unique_dupe_count}")
    
    print(f"\nCross-file duplicates: {len(cross_file_dupes)}")
    if cross_file_dupes:
        total_cross = sum(len(v) for v in cross_file_dupes.values())
        print(f"  Total cross-file duplicate transactions: {total_cross}")
    
    # File overlap analysis
    print("\n3. File Overlap Analysis:")
    for name in file_transactions:
        txns = file_transactions[name]
        if not txns:
            continue
        
        # Check how many appear in other files
        overlap_count = 0
        for txn in txns:
            key = exact_key(txn)
            if key in exact_groups and len(exact_groups[key]) > 1:
                overlap_count += 1
        
        overlap_pct = (overlap_count / len(txns) * 100) if txns else 0
        print(f"   {name}: {len(txns)} txns, {overlap_count} duplicated ({overlap_pct:.1f}%)")
    
    # Show examples
    if cross_file_dupes:
        print("\n4. Cross-File Duplicate Examples:")
        for i, (key, txns) in enumerate(list(cross_file_dupes.items())[:10]):
            date, vendor, amount = key.split('|', 2)
            files = [t['source_file'] for t in txns]
            file_counts = Counter(files)
            print(f"\n   {i+1}. {date} | {vendor[:40]} | ${amount}")
            print(f"      Appears in: {dict(file_counts)}")
    
    # Date range overlap
    print("\n5. Date Range by File:")
    for name in sorted(file_transactions.keys()):
        txns = file_transactions[name]
        if not txns:
            continue
        dates = [t['date'] for t in txns]
        print(f"   {name}: {min(dates)} to {max(dates)}")
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    main()
