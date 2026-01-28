#!/usr/bin/env python3
"""
Parse 2012 PDF Extracts and Stage Data
======================================

Parses extracted text from:
- CIBC banking statements (jan-mar, apr-may, jun-dec)
- QuickBooks reconciliation report

Extracts transactions and saves to CSV staging files.

Safe: Read-only parsing, writes to staging CSVs.
"""
from __future__ import annotations

import os
import re
import csv
from datetime import datetime
from pathlib import Path


STAGING_DIR = r"L:\limo\staging\2012_pdf_extracts"
OUTPUT_DIR = r"L:\limo\staging\2012_parsed"


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def parse_cibc_statement(text: str, filename: str) -> list[dict]:
    """Parse CIBC banking statement transactions"""
    transactions = []
    
    # Pattern for transaction lines
    # Format: Date Description Withdrawals($) Deposits($) Balance($)
    # Example: Jan 3 PURCHASE000001198103 63.50 7,113.84
    
    lines = text.split('\n')
    current_date = None
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # Look for date patterns (Jan 3, Jan 10, etc.)
        date_match = re.match(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})\s+(.+)$', line)
        if date_match:
            month, day, rest = date_match.groups()
            
            # Determine year from filename
            year = "2012"
            current_date = f"{month} {day}, {year}"
            
            # Parse the transaction details
            # Try to extract description and amounts
            parts = rest.split()
            
            # Look for amounts (numbers with possible decimals and commas)
            amounts = []
            description_parts = []
            
            for part in parts:
                # Check if this looks like a money amount
                if re.match(r'^-?\d{1,3}(?:,\d{3})*(?:\.\d{2})?$', part.replace(',', '')):
                    amounts.append(part.replace(',', ''))
                else:
                    description_parts.append(part)
            
            description = ' '.join(description_parts)
            
            # Determine withdrawal, deposit, balance
            withdrawal = None
            deposit = None
            balance = None
            
            if len(amounts) >= 2:
                # Last is typically balance
                balance = amounts[-1]
                # Second-to-last is typically the transaction amount
                amount = amounts[-2]
                
                # Check next line for description continuation
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not re.match(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d', next_line):
                        description += ' ' + next_line
                
                # Determine if withdrawal or deposit based on description keywords
                desc_upper = description.upper()
                if any(kw in desc_upper for kw in ['PURCHASE', 'WITHDRAWAL', 'PAYMENT', 'CHEQUE', 'TRANSFER', 'MEMO']):
                    if 'CREDIT MEMO' in desc_upper or 'DEPOSIT' in desc_upper or 'E-TRANSFER RECLAIM' in desc_upper:
                        deposit = amount
                    else:
                        withdrawal = amount
                elif any(kw in desc_upper for kw in ['DEPOSIT', 'CREDIT']):
                    deposit = amount
                else:
                    # Default: if amount is negative, it's a withdrawal
                    if amount.startswith('-'):
                        withdrawal = amount[1:]
                    else:
                        withdrawal = amount
            
            if description or amounts:
                transactions.append({
                    'date': current_date,
                    'description': description.strip(),
                    'withdrawal': withdrawal,
                    'deposit': deposit,
                    'balance': balance,
                    'source_file': filename,
                })
    
    return transactions


def parse_quickbooks_reconciliation(text: str) -> list[dict]:
    """Parse QuickBooks reconciliation report"""
    transactions = []
    
    lines = text.split('\n')
    in_transactions = False
    
    for line in lines:
        line = line.strip()
        
        # Look for transaction section headers
        if 'Cleared Transactions' in line or 'New Transactions' in line:
            in_transactions = True
            continue
        
        if 'Ending Balance' in line or 'Page' in line:
            in_transactions = False
            continue
        
        if not in_transactions:
            continue
        
        # Parse transaction lines
        # Format: Type Date Num Name Clr Amount Balance
        # Example: Cheque 01/03/2012 Tsf Paul Richard (v) -2,200.00 -2,200.00
        
        # Look for date pattern MM/DD/YYYY
        date_match = re.search(r'(\d{2}/\d{2}/\d{4})', line)
        if date_match:
            date_str = date_match.group(1)
            
            # Extract amount (look for negative or positive numbers with decimals)
            amount_match = re.search(r'(-?\d{1,3}(?:,\d{3})*\.\d{2})', line)
            if amount_match:
                amount = amount_match.group(1).replace(',', '')
                
                # Extract description (everything between date and amount)
                desc_start = date_match.end()
                desc_end = amount_match.start()
                description = line[desc_start:desc_end].strip()
                
                # Determine if withdrawal or deposit
                withdrawal = None
                deposit = None
                
                if float(amount) < 0:
                    withdrawal = amount[1:]  # Remove negative sign
                else:
                    deposit = amount
                
                transactions.append({
                    'date': date_str,
                    'description': description,
                    'withdrawal': withdrawal,
                    'deposit': deposit,
                    'balance': None,  # QB reconciliation doesn't always show running balance
                    'source_file': 'quickbooks',
                })
    
    return transactions


def main():
    print("=" * 80)
    print("PARSING 2012 PDF EXTRACTS")
    print("=" * 80)
    print()
    
    ensure_dir(OUTPUT_DIR)
    
    all_cibc_transactions = []
    all_qb_transactions = []
    
    # Parse CIBC statements
    cibc_files = [
        '2012cibc banking jan-mar_ocred.txt',
        '2012cibc banking apr- may_ocred.txt',
        '2012cibc banking jun-dec_ocred.txt',
    ]
    
    for filename in cibc_files:
        filepath = os.path.join(STAGING_DIR, filename)
        if not os.path.exists(filepath):
            print(f"[WARN]  File not found: {filename}")
            continue
        
        print(f"📄 Parsing: {filename}")
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
        
        transactions = parse_cibc_statement(text, filename)
        all_cibc_transactions.extend(transactions)
        print(f"   [OK] Extracted {len(transactions)} transactions")
    
    # Parse QuickBooks
    qb_file = '2012 quickbooks_ocred.txt'
    qb_filepath = os.path.join(STAGING_DIR, qb_file)
    
    if os.path.exists(qb_filepath):
        print(f"\n📄 Parsing: {qb_file}")
        with open(qb_filepath, 'r', encoding='utf-8') as f:
            text = f.read()
        
        all_qb_transactions = parse_quickbooks_reconciliation(text)
        print(f"   [OK] Extracted {len(all_qb_transactions)} transactions")
    
    # Save to CSV
    if all_cibc_transactions:
        cibc_csv = os.path.join(OUTPUT_DIR, '2012_cibc_transactions.csv')
        with open(cibc_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['date', 'description', 'withdrawal', 'deposit', 'balance', 'source_file'])
            writer.writeheader()
            writer.writerows(all_cibc_transactions)
        print(f"\n💾 Saved CIBC transactions: {cibc_csv}")
        print(f"   Total: {len(all_cibc_transactions)} transactions")
    
    if all_qb_transactions:
        qb_csv = os.path.join(OUTPUT_DIR, '2012_quickbooks_transactions.csv')
        with open(qb_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['date', 'description', 'withdrawal', 'deposit', 'balance', 'source_file'])
            writer.writeheader()
            writer.writerows(all_qb_transactions)
        print(f"\n💾 Saved QuickBooks transactions: {qb_csv}")
        print(f"   Total: {len(all_qb_transactions)} transactions")
    
    print("\n" + "=" * 80)
    print("PARSING COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
