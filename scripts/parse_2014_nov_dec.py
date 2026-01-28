#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Parse 2014 CIBC Nov-Dec transactions from extracted text files.
Format: Date | Description | Withdrawals ($) | Deposits ($) | Balance ($)
"""

import os
import re
import csv
import hashlib
from pathlib import Path

def parse_nov_dec_transactions():
    """Parse all Nov-Dec pages and extract transactions."""
    
    transactions = []
    input_dir = Path("L:\\limo\\data")
    
    # Month mapping
    month_map = {
        'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
        'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
        'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
    }
    
    # Pattern for date line: "Nov 1" or "Dec 31"
    date_pattern = re.compile(r'^(Nov|Dec)\s+(\d{1,2})\s+')
    
    # Patterns for amounts with optional thousands separator
    amount_pattern = re.compile(r'\$([\d,]+\.\d{2})')
    
    # Read all extracted text files
    text_files = sorted([f for f in input_dir.glob('2014_cibc_nov_dec_page*.txt')])
    
    current_date = None
    current_description_lines = []
    current_debit = None
    current_credit = None
    current_balance = None
    
    for text_file in text_files:
        print(f"Parsing {text_file.name}...", end=" ")
        
        with open(text_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line in lines:
            line = line.rstrip()
            
            # Skip empty lines and headers
            if not line.strip() or 'Transaction details' in line or 'Date' in line and 'Description' in line:
                continue
            
            # Skip footer lines
            if any(x in line for x in ['Closing balance', 'Opening balance', 'CIBC Account Statement', 
                                        'Account number', 'Branch transit', 'Balance forward']):
                # Special case: capture "Closing balance" amount
                if 'Closing balance' in line:
                    match = amount_pattern.search(line)
                    if match:
                        balance_str = match.group(1).replace(',', '')
                        # This is just info, don't create transaction
                continue
            
            # Check if line starts with date (new transaction date)
            date_match = date_pattern.match(line)
            
            if date_match:
                # Save previous transaction if exists
                if current_date and current_description_lines:
                    transactions.append({
                        'date': current_date,
                        'description': ' '.join(current_description_lines).strip(),
                        'debit': current_debit,
                        'credit': current_credit,
                        'balance': current_balance
                    })
                
                # Extract new date
                month_abbr = date_match.group(1)
                day = date_match.group(2)
                month = month_map.get(month_abbr, '00')
                current_date = f"2014-{month}-{int(day):02d}"
                
                # Extract amounts from same line
                rest_of_line = line[date_match.end():].strip()
                current_description_lines = [rest_of_line]
                
                # Extract all amounts from line
                amounts = amount_pattern.findall(rest_of_line)
                if len(amounts) >= 2:
                    # Last amount is always balance
                    current_balance = amounts[-1].replace(',', '')
                    
                    if len(amounts) == 3:
                        # Format: withdrawal | deposit | balance
                        current_debit = amounts[0].replace(',', '')
                        current_credit = amounts[1].replace(',', '')
                    elif len(amounts) == 2:
                        # Format: amount | balance (need to determine if debit or credit)
                        # Default to debit, check description keywords
                        amount = amounts[0].replace(',', '')
                        if any(keyword in rest_of_line.upper() for keyword in 
                               ['DEPOSIT', 'CREDIT MEMO', 'TRANSFER IN', 'ETRANSFER']):
                            current_debit = None
                            current_credit = amount
                        else:
                            current_debit = amount
                            current_credit = None
                else:
                    current_debit = None
                    current_credit = None
                    current_balance = None
            else:
                # Continuation line (part of description)
                if current_date:
                    current_description_lines.append(line.strip())
        
        print("done")
    
    # Don't forget last transaction
    if current_date and current_description_lines:
        transactions.append({
            'date': current_date,
            'description': ' '.join(current_description_lines).strip(),
            'debit': current_debit,
            'credit': current_credit,
            'balance': current_balance
        })
    
    print(f"\nParsed {len(transactions)} transactions from Nov-Dec 2014")
    
    # Write to CSV
    output_csv = Path("L:\\limo\\data\\2014_cibc_nov_dec_transactions.csv")
    
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter='|')
        writer.writerow(['Date', 'Description', 'Withdrawal ($)', 'Deposit ($)', 'Balance ($)', 'Hash'])
        
        for txn in transactions:
            # Generate hash for duplicate detection
            hash_input = f"{txn['date']}|{txn['description']}|{txn['debit'] or ''}|{txn['credit'] or ''}".encode('utf-8')
            source_hash = hashlib.sha256(hash_input).hexdigest()
            
            writer.writerow([
                txn['date'],
                txn['description'],
                txn['debit'] or '',
                txn['credit'] or '',
                txn['balance'] or '',
                source_hash
            ])
    
    print(f"Wrote {len(transactions)} transactions to {output_csv}")
    
    # Sample output
    print("\nSample transactions:")
    for txn in transactions[:5]:
        print(f"  {txn['date']} {txn['description'][:50]:50} D:{txn['debit'] or '':>10} C:{txn['credit'] or '':>10} Bal:{txn['balance'] or '':>10}")

if __name__ == '__main__':
    parse_nov_dec_transactions()
