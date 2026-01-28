#!/usr/bin/env python3
"""
Parse Scotia Bank new statement format (Dec 2012 - Jan 2013 style).

Key format differences:
- Amount appears ABOVE date line (e.g., "594 98" for $594.98)
- Date on separate line in MM/DD/YYYY format
- Description can span multiple lines
- Balance appears aligned with date line

Example:
DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH
                                594 98 01/02/2013
"""

import re
from datetime import datetime
from decimal import Decimal

def parse_amount(amount_str):
    """Parse amount like '594 98' to 594.98"""
    parts = amount_str.strip().split()
    if len(parts) == 2:
        dollars = parts[0].replace(',', '')
        cents = parts[1].zfill(2)  # Pad cents to 2 digits (4 → 04)
        return Decimal(f"{dollars}.{cents}")
    elif len(parts) == 1:
        # Single value, assume it's already complete
        return Decimal(parts[0].replace(',', ''))
    return None

def parse_statement_text(text_lines):
    """
    Parse Scotia statement text in new format.
    
    Returns list of transactions: (date, description, amount, balance)
    """
    transactions = []
    i = 0
    
    while i < len(text_lines):
        line = text_lines[i].strip()
        
        # Skip empty lines and headers
        if not line or 'DESCRIPTION' in line or 'BALANCE FORWARD' in line:
            i += 1
            continue
        
        # Look for date pattern on current or next line
        # Date format: MM/DD/YYYY possibly with balance after
        date_match = re.search(r'(\d{2}/\d{2}/\d{4})', line)
        
        if date_match:
            # This line has a date, look backwards for description and amount
            date_str = date_match.group(1)
            trans_date = datetime.strptime(date_str, '%m/%d/%Y').date()
            
            # Extract balance if present (rightmost number on date line)
            balance_match = re.search(r'(\d{1,3}(?:,?\d{3})*)\s+(\d{2})\s*$', line)
            balance = None
            if balance_match:
                balance = parse_amount(f"{balance_match.group(1)} {balance_match.group(2)}")
            
            # Look for amount just before date (same line or line above)
            amount = None
            amount_line = line[:date_match.start()].strip()
            amount_match = re.search(r'(\d{1,3}(?:,?\d{3})*)\s+(\d{2})\s*$', amount_line)
            
            if not amount_match and i > 0:
                # Check previous line for amount
                prev_line = text_lines[i-1].strip()
                amount_match = re.search(r'(\d{1,3}(?:,?\d{3})*)\s+(\d{2})\s*$', prev_line)
            
            if amount_match:
                amount = parse_amount(f"{amount_match.group(1)} {amount_match.group(2)}")
            
            # Build description from previous lines until we hit another date or start
            description_parts = []
            j = i - 1
            while j >= 0:
                prev = text_lines[j].strip()
                if not prev:
                    break
                # Stop if we hit another date
                if re.search(r'\d{2}/\d{2}/\d{4}', prev):
                    break
                # Remove amount from line if present
                desc = re.sub(r'\d{1,3}(?:,?\d{3})*\s+\d{2}\s*$', '', prev).strip()
                if desc:
                    description_parts.insert(0, desc)
                j -= 1
            
            description = ' '.join(description_parts) if description_parts else 'UNKNOWN'
            
            transactions.append({
                'date': trans_date,
                'description': description,
                'amount': amount,
                'balance': balance
            })
        
        i += 1
    
    return transactions

def determine_debit_credit(description, amount):
    """
    Determine if transaction is debit or credit based on description keywords.
    
    Credits (money IN):
    - DEPOSIT
    - CREDIT MEMO
    - Merchant deposits
    
    Debits (money OUT):
    - Everything else
    """
    desc_upper = description.upper()
    
    # Credits
    if any(x in desc_upper for x in ['DEPOSIT', 'CREDIT MEMO', 'DEP CR']):
        return (None, amount)  # (debit, credit)
    
    # Debits
    return (amount, None)

# Test with provided data
if __name__ == '__main__':
    test_data = """DESCRIPTION
BALANCE FORWARD
DEPOSIT
DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH
                                594 98 01/02/2013
DEPOSIT 087384700019 00001 DEBIT CD DEP CR CHASE PAYMENTECH
                                102 35 01/02/2013
DEPOSIT 087384700019 00001 VISA DEBIT CD CHASE PAYMENTECH
                                165 01/02/2013
DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH
                                205 01/02/2013
RENT/LEASES A0000<DEFTPYMT> ACE TRUCK RENTALS LTD.
                                2695 4 01/02/2013
AUTO LEASE HEFFNER AUTO FC
                                889 7 01/02/2013
AUTO LEASE HEFFNER AUTO FC
                                471 89 01/02/2013
POINT OF SALE PURCHASE CINEPLEX #3132 QPS RED DEER
                                54 01 01/02/2013"""
    
    lines = test_data.split('\n')
    transactions = parse_statement_text(lines)
    
    print(f"\nParsed {len(transactions)} transactions:\n")
    for t in transactions:
        debit, credit = determine_debit_credit(t['description'], t['amount'])
        print(f"{t['date']} | {t['description'][:60]:60s} | D:{debit or 0:8.2f} C:{credit or 0:8.2f} | Bal:{t['balance'] or 0:8.2f}")
