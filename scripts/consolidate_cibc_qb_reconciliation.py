#!/usr/bin/env python3
"""
Consolidate CIBC QuickBooks reconciliation data with deduplication.

Same process as Scotia Bank:
- Parse reconciliation PDF (OCR text)
- Remove header/total lines
- Deduplicate transactions across multiple report pages
- Track cheque numbers
- Export to CSV for banking import

Input: "L:\limo\pdf\2012\pdf2012 quickbooks cibc bank reconciliation detailed_ocred.pdf"
Output: l:\limo\data\cibc_qb_reconciliation_consolidated.csv

Created: November 25, 2025
"""

import pdfplumber
import csv
import re
import hashlib
from datetime import datetime
from collections import defaultdict
from decimal import Decimal

PDF_PATH = r"L:\limo\pdf\2012\pdf2012 quickbooks cibc bank reconciliation detailed_ocred.pdf"
OUTPUT_CSV = r"l:\limo\data\cibc_qb_reconciliation_consolidated.csv"

# Transaction type patterns (handle OCR errors)
TRANSACTION_TYPES = {
    'cheque': r'(?i)chequ?e?s?',
    'deposit': r'(?i)deposit',
    'bill_pmt': r'(?i)bill\s*pm?t?',
    'general_journal': r'(?i)general\s*[jJ]?ournal',
    'debit': r'(?i)debit',
    'credit': r'(?i)credit',
    'transfer': r'(?i)transfer',
    'withdrawal': r'(?i)withdraw',
}

def normalize_transaction_type(type_str):
    """Normalize transaction type with OCR error handling."""
    if not type_str:
        return "Unknown"
    
    type_upper = type_str.strip().upper()
    
    # Handle common OCR errors
    type_upper = type_upper.replace('CHEQUS', 'CHEQUE')
    type_upper = type_upper.replace('CHEQU', 'CHEQUE')
    type_upper = type_upper.replace('CHQ', 'CHEQUE')
    type_upper = type_upper.replace('PM!', 'PMT')
    type_upper = type_upper.replace('GENERAI', 'GENERAL')
    type_upper = type_upper.replace('JOURNAI', 'JOURNAL')
    
    # Standardize to common types
    if 'CHEQUE' in type_upper:
        return "Cheque"
    elif 'DEPOSIT' in type_upper:
        return "Deposit"
    elif 'BILL' in type_upper and 'PMT' in type_upper:
        return "Bill Pmt"
    elif 'GENERAL' in type_upper and 'JOURNAL' in type_upper:
        return "General Journal"
    elif 'DEBIT' in type_upper:
        return "Debit Memo"
    elif 'CREDIT' in type_upper:
        return "Credit Memo"
    elif 'TRANSFER' in type_upper:
        return "Transfer"
    elif 'WITHDRAW' in type_upper:
        return "Withdrawal"
    else:
        return type_str.strip()

def parse_amount(amount_str):
    """Parse amount string to float, handling negatives and commas."""
    if not amount_str or amount_str == '-':
        return 0.0
    
    # Remove commas, spaces, dollar signs
    cleaned = amount_str.replace(',', '').replace('$', '').replace(' ', '').strip()
    
    # Handle negative in parentheses
    if cleaned.startswith('(') and cleaned.endswith(')'):
        cleaned = '-' + cleaned[1:-1]
    
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

def parse_date(date_str):
    """Parse date string in MM/DD/YYYY format."""
    if not date_str:
        return None
    
    try:
        # Try MM/DD/YYYY
        return datetime.strptime(date_str.strip(), '%m/%d/%Y').date()
    except ValueError:
        try:
            # Try M/D/YYYY
            return datetime.strptime(date_str.strip(), '%m/%d/%Y').date()
        except ValueError:
            return None

def is_header_or_total_line(line):
    """Check if line is a header or total line to skip."""
    line_upper = line.upper()
    
    skip_patterns = [
        'TYPE', 'DATE', 'NUM', 'NAME', 'AMOUNT', 'BALANCE',
        'CLEARED TRANSACTIONS', 'NEW TRANSACTIONS',
        'DEPOSITS AND CREDITS', 'CHEQUES AND PAYMENTS',
        'TOTAL DEPOSITS', 'TOTAL CHEQUES', 'TOTAL PAYMENTS',
        'BEGINNING BALANCE', 'ENDING BALANCE',
        'PAGE', 'CIBC', 'ARROW LIMOUSINE',
        '------', '======', '______',
    ]
    
    for pattern in skip_patterns:
        if pattern in line_upper:
            return True
    
    return False

def extract_transactions_from_pdf(pdf_path):
    """Extract transaction lines from PDF."""
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
            
            lines = text.split('\n')
            print(f"  Found {len(lines)} lines")
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Skip headers and totals
                if is_header_or_total_line(line):
                    continue
                
                # Parse transaction line
                # Format: Type Date Num Name Amount Balance
                parts = line.split()
                if len(parts) < 4:
                    continue
                
                # Extract components
                tx_type = parts[0]
                
                # Handle multi-word types (Bill Pmt -Cheque)
                type_end_idx = 1
                if len(parts) > 1 and (parts[1].startswith('-') or parts[0] == 'Bill'):
                    tx_type = parts[0] + ' ' + parts[1]
                    type_end_idx = 2
                
                # Date should be next
                if type_end_idx >= len(parts):
                    continue
                
                date_str = parts[type_end_idx]
                tx_date = parse_date(date_str)
                if not tx_date:
                    continue
                
                # Remaining parts: Num Name ... Amount Balance
                remaining = parts[type_end_idx + 1:]
                if len(remaining) < 2:
                    continue
                
                # Balance is last
                balance = parse_amount(remaining[-1])
                
                # Amount is second to last
                amount = parse_amount(remaining[-2])
                
                # Num is first of remaining
                num = remaining[0]
                
                # Name is middle parts
                name_parts = remaining[1:-2] if len(remaining) > 2 else []
                name = ' '.join(name_parts) if name_parts else ''
                
                # Normalize type
                tx_type_normalized = normalize_transaction_type(tx_type)
                
                transaction = {
                    'type': tx_type_normalized,
                    'date': tx_date,
                    'num': num,
                    'name': name,
                    'amount': amount,
                    'balance': balance,
                    'source_page': page_num,
                    'raw_line': line
                }
                
                transactions.append(transaction)
    
    print(f"\nTotal transactions extracted: {len(transactions)}")
    return transactions

def deduplicate_transactions(transactions):
    """Deduplicate transactions using hash of key fields."""
    print(f"\nDeduplicating {len(transactions)} transactions...")
    
    # Group by unique key (date, type, amount, name)
    grouped = defaultdict(list)
    
    for txn in transactions:
        # Create hash key
        key_str = f"{txn['date']}|{txn['type']}|{txn['amount']:.2f}|{txn['name']}"
        hash_key = hashlib.sha256(key_str.encode('utf-8')).hexdigest()
        grouped[hash_key].append(txn)
    
    # Keep first occurrence, track duplicates
    unique_transactions = []
    duplicate_count = 0
    
    for hash_key, txn_list in grouped.items():
        # Keep first transaction
        first_txn = txn_list[0]
        first_txn['appears_in_pages'] = [t['source_page'] for t in txn_list]
        first_txn['duplicate_count'] = len(txn_list) - 1
        
        unique_transactions.append(first_txn)
        duplicate_count += len(txn_list) - 1
    
    print(f"Unique transactions: {len(unique_transactions)}")
    print(f"Duplicates removed: {duplicate_count}")
    print(f"Deduplication rate: {duplicate_count / len(transactions) * 100:.1f}%")
    
    return unique_transactions

def export_to_csv(transactions, output_path):
    """Export transactions to CSV."""
    print(f"\nExporting to CSV: {output_path}")
    
    # Sort by date, then type
    sorted_txns = sorted(transactions, key=lambda x: (x['date'], x['type'], x['amount']))
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Header
        writer.writerow(['date', 'type', 'num', 'name', 'amount', 'balance', 
                        'appears_in_pages', 'duplicate_count'])
        
        # Data rows
        for txn in sorted_txns:
            pages = ','.join(map(str, txn['appears_in_pages']))
            writer.writerow([
                txn['date'].strftime('%Y-%m-%d'),
                txn['type'],
                txn['num'],
                txn['name'],
                f"{txn['amount']:.2f}",
                f"{txn['balance']:.2f}",
                pages,
                txn['duplicate_count']
            ])
    
    print(f"Exported {len(sorted_txns)} transactions")

def analyze_transactions(transactions):
    """Print analysis of transactions."""
    print("\n" + "="*80)
    print("TRANSACTION ANALYSIS")
    print("="*80)
    
    # By type
    by_type = defaultdict(lambda: {'count': 0, 'total': 0.0})
    for txn in transactions:
        by_type[txn['type']]['count'] += 1
        by_type[txn['type']]['total'] += txn['amount']
    
    print("\nBy Type:")
    for tx_type in sorted(by_type.keys()):
        stats = by_type[tx_type]
        print(f"  {tx_type:30} | {stats['count']:5} txns | ${stats['total']:>12,.2f}")
    
    # Date range
    dates = [txn['date'] for txn in transactions]
    print(f"\nDate Range:")
    print(f"  First: {min(dates)}")
    print(f"  Last: {max(dates)}")
    
    # Cheques
    cheques = [txn for txn in transactions if 'cheque' in txn['type'].lower()]
    print(f"\nCheques: {len(cheques)} transactions")
    if cheques:
        print(f"  Total: ${sum(txn['amount'] for txn in cheques):,.2f}")

def main():
    print("="*80)
    print("CIBC QUICKBOOKS RECONCILIATION CONSOLIDATION")
    print("="*80)
    
    # Extract transactions from PDF
    transactions = extract_transactions_from_pdf(PDF_PATH)
    
    if not transactions:
        print("\nNo transactions found!")
        return
    
    # Deduplicate
    unique_transactions = deduplicate_transactions(transactions)
    
    # Export to CSV
    export_to_csv(unique_transactions, OUTPUT_CSV)
    
    # Analysis
    analyze_transactions(unique_transactions)
    
    print("\n" + "="*80)
    print("COMPLETE")
    print("="*80)
    print(f"\nOutput file: {OUTPUT_CSV}")
    print("\nNext steps:")
    print("1. Review CSV for accuracy")
    print("2. Compare against banking_transactions (account 0228362)")
    print("3. Import missing transactions to database")
    print("4. Create receipts for unmatched banking transactions")

if __name__ == '__main__':
    main()
