#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Parse 2014 CIBC PDF text files and create CSV for import.
Handles multiple text files with transaction data.
"""
import os
import re
import csv
from datetime import datetime
from decimal import Decimal
import glob

def parse_transaction_line(line):
    """
    Parse a transaction line like:
    June 25, 2014 Electronic Funds TransferNETWORKTRANSACTION FEEABM- $1.50 $77.21
    
    Returns: (date, description, debit/credit, balance) or None
    """
    # Match date pattern at start: Month DD, YYYY or Month. DD, YYYY
    date_pattern = r'^([A-Za-z]{3,9}\.?\s+\d{1,2},\s+\d{4})\s+'
    match = re.match(date_pattern, line)
    if not match:
        return None
    
    date_str = match.group(1)
    rest = line[match.end():]
    
    # Find dollar amounts at end: $amount $balance
    # Format: ... $1.50 $77.21 or ... $1,234.56 $5,678.90
    amount_pattern = r'\$([0-9,]+\.\d{2})\s+\$([0-9,]+\.\d{2})$'
    amount_match = re.search(amount_pattern, rest)
    
    if not amount_match:
        return None
    
    # Description is everything between date and amounts
    description = rest[:amount_match.start()].strip()
    amount = Decimal(amount_match.group(1).replace(',', ''))
    balance = Decimal(amount_match.group(2).replace(',', ''))
    
    # Parse date
    try:
        date_str_clean = date_str.replace('.', '').strip()  # Remove periods
        # Handle "Sept" → "Sep"
        date_str_clean = date_str_clean.replace('Sept ', 'Sep ')
        date = datetime.strptime(date_str_clean, '%B %d, %Y').date()
    except:
        try:
            date = datetime.strptime(date_str_clean, '%b %d, %Y').date()
        except Exception as e:
            print(f"Could not parse date: '{date_str}' -> '{date_str_clean}' ({e})")
            return None
    
    return (date, description, amount, balance)

def detect_debit_or_credit(description, prev_balance, amount, new_balance):
    """
    Determine if amount is debit (withdrawal) or credit (deposit).
    Use transaction type keywords from CIBC statement format.
    """
    desc_upper = description.upper()
    
    # Deposits (credits) - money coming IN
    deposit_keywords = ['DEPOSIT', 'CREDIT MEMO', 'CORRECTION', 'REFUND', 'REVERSAL']
    if any(kw in desc_upper for kw in deposit_keywords):
        return (Decimal('0'), amount)
    
    # Withdrawals (debits) - money going OUT
    withdrawal_keywords = ['WITHDRAW', 'PURCHASE', 'DEBIT', 'FEE', 'NSF', 'CHEQUE', 
                           'INSURANCE', 'PAYMENT', 'TRANSFER', 'PAD', 'PRE-AUTH', 
                           'PREAUTHORIZED', 'SERVICE CHARGE', 'S/C']
    if any(kw in desc_upper for kw in withdrawal_keywords):
        return (amount, Decimal('0'))
    
    # Fallback to balance comparison if keywords don't match
    if prev_balance is not None:
        expected_with_credit = prev_balance + amount
        expected_with_debit = prev_balance - amount
        
        # Which is closer to actual new balance?
        if abs(expected_with_credit - new_balance) < abs(expected_with_debit - new_balance):
            return (Decimal('0'), amount)  # Credit
        else:
            return (amount, Decimal('0'))  # Debit
    
    # Default: treat as debit
    return (amount, Decimal('0'))

# Parse all text files
text_files = sorted(glob.glob('l:\\limo\\data\\2014_cibc2_page*.txt'))
print(f"Found {len(text_files)} text files to parse")

transactions = []
for txt_file in text_files:
    print(f"Parsing: {txt_file}")
    with open(txt_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for line in lines:
        result = parse_transaction_line(line)
        if result:
            transactions.append(result)

print(f"\nParsed {len(transactions)} transactions")

# Sort by date and balance to establish chronological order
transactions.sort(key=lambda t: (t[0], t[3]))

# Determine debit/credit for each transaction
final_transactions = []
prev_balance = None

for date, description, amount, balance in transactions:
    debit, credit = detect_debit_or_credit(description, prev_balance, amount, balance)
    final_transactions.append((date, description, debit, credit, balance))
    prev_balance = balance

# Write to CSV
csv_file = 'l:\\limo\\data\\2014_cibc_pdf_transactions.csv'
with open(csv_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f, delimiter='|')
    for date, description, debit, credit, balance in final_transactions:
        writer.writerow([date.strftime('%b. %d, %Y'), description, 
                        debit if debit > 0 else '', 
                        credit if credit > 0 else '', 
                        balance])

print(f"\nWrote {len(final_transactions)} transactions to: {csv_file}")
print("\nSample transactions:")
for i, (date, description, debit, credit, balance) in enumerate(final_transactions[:10]):
    d_str = f"${debit:.2f}" if debit > 0 else ""
    c_str = f"${credit:.2f}" if credit > 0 else ""
    print(f"  {date} {description[:50]:50} D:{d_str:10} C:{c_str:10} Bal:${balance:.2f}")

if len(final_transactions) > 10:
    print(f"  ... and {len(final_transactions) - 10} more")
