#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Extract complete Feb-Mar 2012 CIBC 1615 statement data for database import."""

import pdfplumber
import re
from datetime import datetime
import json

pdf_path = r'L:\limo\pdf\2012\pdf2012cibc banking jan-mar_ocred.pdf'

def parse_amount(amount_str):
    """Parse dollar amount string to float."""
    if not amount_str:
        return 0.0
    # Remove $ and commas, handle negative
    amount_str = amount_str.strip().replace('$', '').replace(',', '')
    try:
        return float(amount_str)
    except:
        return 0.0

def extract_statement_data(text, month_name):
    """Extract complete statement with all transactions."""
    
    data = {
        'month': month_name,
        'opening_balance': None,
        'closing_balance': None,
        'transactions': []
    }
    
    lines = text.split('\n')
    
    # Find opening balance line
    for i, line in enumerate(lines):
        if 'Opening balance on' in line:
            # Try to extract amount from this line or next
            match = re.search(r'\$\s*([0-9,.-]+)', line)
            if match:
                data['opening_balance'] = parse_amount(match.group(1))
            elif i + 1 < len(lines):
                match = re.search(r'\$\s*([0-9,.-]+)', lines[i + 1])
                if match:
                    data['opening_balance'] = parse_amount(match.group(1))
    
    # Find closing balance line
    for i, line in enumerate(lines):
        if 'Closing balance on' in line or 'Balance on' in line and 'Closing' in line:
            match = re.search(r'\$\s*([0-9,.-]+)', line)
            if match:
                data['closing_balance'] = parse_amount(match.group(1))
            elif i + 1 < len(lines):
                match = re.search(r'\$\s*([0-9,.-]+)', lines[i + 1])
                if match:
                    data['closing_balance'] = parse_amount(match.group(1))
    
    # Extract all transaction lines
    month_short = month_name[:3]
    current_balance = data['opening_balance']
    
    for line in lines:
        # Match transaction lines: "Feb 16 DESCRIPTION ... 1,072.12" format
        if re.match(rf'^{month_short}\s+\d+', line.strip()):
            # Parse date
            date_match = re.match(rf'^({month_short})\s+(\d+)', line.strip())
            if not date_match:
                continue
            
            day = int(date_match.group(2))
            if month_name == 'February':
                date_str = f"2012-02-{day:02d}"
            elif month_name == 'March':
                date_str = f"2012-03-{day:02d}"
            else:
                continue
            
            # Extract description and amounts
            # Format varies: "Feb 16 Description DEBIT AMOUNT CREDIT AMOUNT BALANCE"
            
            # Try to find all numbers (amounts and balance)
            amounts = re.findall(r'\$?\s*([0-9,.-]+)', line)
            
            if len(amounts) >= 2:
                # Last amount is usually the balance
                balance = parse_amount(amounts[-1])
                
                # Try to identify debit vs credit
                # If line has DEPOSIT/CREDIT - it's a deposit
                # Otherwise it's a withdrawal
                
                is_deposit = bool(re.search(r'DEPOSIT|CREDIT MEMO|TRANSFER IN', line, re.IGNORECASE))
                is_withdrawal = bool(re.search(r'PURCHASE|WITHDRAWAL|PAYMENT|DEBIT|FEE|CHQ', line, re.IGNORECASE))
                
                # Get the transaction amount (second to last amount usually)
                if len(amounts) >= 2:
                    txn_amount = parse_amount(amounts[-2])
                else:
                    txn_amount = 0
                
                # Clean description
                desc = line.strip()
                
                data['transactions'].append({
                    'date': date_str,
                    'description': desc,
                    'amount': txn_amount,
                    'is_deposit': is_deposit,
                    'is_withdrawal': is_withdrawal,
                    'balance': balance
                })
    
    return data

with pdfplumber.open(pdf_path) as pdf:
    print("=" * 100)
    print("EXTRACTING FEBRUARY 2012")
    print("=" * 100)
    
    # Extract February
    feb_text = ""
    for page_num in range(15, 21):
        if page_num < len(pdf.pages):
            feb_text += pdf.pages[page_num].extract_text() + "\n"
    
    feb_data = extract_statement_data(feb_text, 'February')
    print(f"Opening: {feb_data['opening_balance']}")
    print(f"Closing: {feb_data['closing_balance']}")
    print(f"Transactions: {len(feb_data['transactions'])}")
    
    if feb_data['transactions']:
        print("\nTransaction details:")
        for txn in feb_data['transactions']:
            print(f"  {txn['date']} | Amt: ${txn['amount']:8.2f} | D:{txn['is_deposit']} W:{txn['is_withdrawal']} | Bal: ${txn['balance']:10.2f}")
            print(f"    Desc: {txn['description'][:70]}")
    
    print("\n" + "=" * 100)
    print("EXTRACTING MARCH 2012")
    print("=" * 100)
    
    # Extract March
    mar_text = ""
    for page_num in range(25, 31):
        if page_num < len(pdf.pages):
            mar_text += pdf.pages[page_num].extract_text() + "\n"
    
    mar_data = extract_statement_data(mar_text, 'March')
    print(f"Opening: {mar_data['opening_balance']}")
    print(f"Closing: {mar_data['closing_balance']}")
    print(f"Transactions: {len(mar_data['transactions'])}")
    
    if mar_data['transactions']:
        print("\nTransaction details:")
        for txn in mar_data['transactions']:
            print(f"  {txn['date']} | Amt: ${txn['amount']:8.2f} | D:{txn['is_deposit']} W:{txn['is_withdrawal']} | Bal: ${txn['balance']:10.2f}")
            print(f"    Desc: {txn['description'][:70]}")
    
    print("\n" + "=" * 100)
    print("✅ DATA EXTRACTED - Ready for database import")
    print("=" * 100)
    
    # Save to JSON for next step
    import_data = {
        'February': feb_data,
        'March': mar_data,
        'January_expected_closing': -49.17,
        'notes': 'Extracted from L:\\limo\\pdf\\2012\\pdf2012cibc banking jan-mar_ocred.pdf'
    }
    
    with open(r'L:\limo\data\feb_mar_2012_extracted.json', 'w') as f:
        json.dump(import_data, f, indent=2, default=str)
    
    print("\n✅ Data saved to: L:\\limo\\data\\feb_mar_2012_extracted.json")
