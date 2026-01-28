#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Parse 2014 CIBC Nov-Dec transactions from monthly statement format.
Format: Date | Description | Withdrawals ($) | Deposits ($) | Balance ($)
Using only pages 47-52 (Nov) and 53-60 (Dec)
"""

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
        'Nov': '11', 'Dec': '12'
    }
    
    # Read only Nov-Dec pages
    text_files = sorted([
        f for f in input_dir.glob('2014_cibc_nov_dec_page*.txt') 
        if int(f.name.split('page')[1].split('.')[0]) >= 47
    ])
    
    print(f"Parsing {len(text_files)} pages...")
    
    accumulated_lines = []
    
    for text_file in text_files:
        with open(text_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line in lines:
            line = line.rstrip()
            accumulated_lines.append(line)
    
    # Now parse accumulated lines
    print(f"Processing {len(accumulated_lines)} lines...")
    
    current_date = None
    description_lines = []
    amounts_on_line = []
    
    i = 0
    while i < len(accumulated_lines):
        line = accumulated_lines[i].strip()
        i += 1
        
        # Skip empty lines
        if not line:
            continue
        
        # Skip headers and footers
        if any(x in line for x in ['Transaction details', 'Date', 'Description', 
                                     'CIBC Account Statement', 'Account number',
                                     'Branch transit', 'Important:', 'Bankbook',
                                     'Statement:', 'Foreign Currency', 'Trademark',
                                     'Page', 'PER-2016']):
            continue
        
        # Check for date at start of line (e.g., "Nov 1" or "Dec 31")
        date_match = re.match(r'^(Nov|Dec)\s+(\d{1,2})\s+', line)
        
        if date_match:
            # Save previous transaction if we have one
            if current_date and description_lines:
                # Extract amounts from collected lines
                debit, credit, balance = extract_amounts_from_description(''.join(description_lines))
                
                if debit or credit or balance:
                    transactions.append({
                        'date': current_date,
                        'description': ' '.join([l.strip() for l in description_lines if l.strip()]),
                        'debit': debit,
                        'credit': credit,
                        'balance': balance
                    })
            
            # Start new transaction
            month_abbr = date_match.group(1)
            day = date_match.group(2)
            month = month_map.get(month_abbr, '00')
            current_date = f"2014-{month}-{int(day):02d}"
            
            # Rest of line is description start
            rest = line[date_match.end():].strip()
            description_lines = [rest] if rest else []
        
        elif current_date:
            # This is part of current transaction description
            description_lines.append(line)
    
    # Don't forget last transaction
    if current_date and description_lines:
        debit, credit, balance = extract_amounts_from_description(''.join(description_lines))
        if debit or credit or balance:
            transactions.append({
                'date': current_date,
                'description': ' '.join([l.strip() for l in description_lines if l.strip()]),
                'debit': debit,
                'credit': credit,
                'balance': balance
            })
    
    print(f"\nParsed {len(transactions)} transactions from Nov-Dec 2014")
    
    # Write to CSV
    output_csv = Path("L:\\limo\\data\\2014_cibc_nov_dec_transactions.csv")
    
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter='|')
        writer.writerow(['Date', 'Description', 'Withdrawal ($)', 'Deposit ($)', 'Balance ($)', 'Hash'])
        
        for txn in transactions:
            # Generate hash for duplicate detection
            hash_input = f"{txn['date']}|{txn['description'][:100]}|{txn['debit'] or ''}|{txn['credit'] or ''}".encode('utf-8')
            source_hash = hashlib.sha256(hash_input).hexdigest()
            
            writer.writerow([
                txn['date'],
                txn['description'][:200],
                txn['debit'] or '',
                txn['credit'] or '',
                txn['balance'] or '',
                source_hash
            ])
    
    print(f"Wrote {len(transactions)} transactions to {output_csv}")
    
    # Sample output
    print("\nFirst 10 transactions:")
    for i, txn in enumerate(transactions[:10]):
        print(f"{i+1}. {txn['date']} | {txn['description'][:60]:60} | D:{txn['debit'] or '-':>10} | C:{txn['credit'] or '-':>10} | Bal:{txn['balance'] or '-':>10}")

def extract_amounts_from_description(text):
    """Extract withdrawal, deposit, and balance amounts from text."""
    # Pattern for amounts: $12,345.67
    amount_pattern = r'\$[\d,]+\.\d{2}'
    matches = re.findall(amount_pattern, text)
    
    amounts = [m[1:].replace(',', '') for m in matches]  # Remove $ and comma
    
    debit = None
    credit = None
    balance = None
    
    if len(amounts) >= 3:
        # Last is always balance
        balance = amounts[-1]
        # Second to last is first amount (check if deposit or withdrawal)
        # This is tricky - need to check description keywords
        first_amount = amounts[-2]
        if any(kw in text.upper() for kw in ['DEPOSIT', 'CREDIT', 'ETRANSFER', 'TRANSFER IN']):
            credit = first_amount
        else:
            debit = first_amount
    elif len(amounts) == 2:
        # Last is balance
        balance = amounts[-1]
        # Check if first is deposit or withdrawal
        if any(kw in text.upper() for kw in ['DEPOSIT', 'CREDIT', 'ETRANSFER', 'TRANSFER IN']):
            credit = amounts[0]
        else:
            debit = amounts[0]
    elif len(amounts) == 1:
        balance = amounts[0]
    
    return debit, credit, balance

if __name__ == '__main__':
    parse_nov_dec_transactions()
