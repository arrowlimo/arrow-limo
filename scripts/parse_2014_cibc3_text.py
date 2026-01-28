#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Parse 2014 CIBC statement (format 3) - monthly statement format.

This format has:
- Date Description Withdrawals ($) Deposits($) Balance($)
- Monthly pages (Jan 1-31, Feb 1-28, etc.)
"""

import re
import csv
import glob
import hashlib
from datetime import datetime
from decimal import Decimal

def parse_transaction_line(line, current_year=2014):
    """
    Parse transaction line from monthly statement format.
    Format: "Date Description Withdrawals ($) Deposits($) Balance($)"
    Example: "Jan 2 PREAUTHORIZEDDEBIT 1,371.23 468.19"
    """
    # Skip non-transaction lines
    if not line.strip():
        return None
    
    # Match date at start (month abbreviation + day)
    date_pattern = r'^([A-Za-z]{3})\s+(\d{1,2})\s+'
    date_match = re.match(date_pattern, line)
    
    if not date_match:
        return None
    
    month_str = date_match.group(1)
    day = int(date_match.group(2))
    
    # Parse month
    month_map = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
        'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
    }
    
    if month_str not in month_map:
        return None
    
    month = month_map[month_str]
    
    # Rest of line after date
    rest = line[date_match.end():].strip()
    
    # Look for amounts at end: withdrawal deposit balance
    # Pattern: three numbers (with optional commas and decimals)
    amounts_pattern = r'([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$'
    amounts_match = re.search(amounts_pattern, rest)
    
    if amounts_match:
        # Format: description withdrawal balance OR description deposit balance
        description = rest[:amounts_match.start()].strip()
        amt1 = Decimal(amounts_match.group(1).replace(',', ''))
        amt2 = Decimal(amounts_match.group(2).replace(',', ''))
        
        # Determine if amt1 is withdrawal or deposit by checking which makes sense
        # The second number is always the balance
        balance = amt2
        
        # If description contains deposit keywords, amt1 is deposit
        if any(kw in description.upper() for kw in ['DEPOSIT', 'TRANSFER000', 'E-TRANSFER', 'CORRECTION']):
            withdrawal = Decimal('0')
            deposit = amt1
        else:
            # Otherwise it's a withdrawal
            withdrawal = amt1
            deposit = Decimal('0')
        
        date = datetime(current_year, month, day).date()
        return (date, description, withdrawal, deposit, balance)
    
    # Try three amounts: withdrawal deposit balance
    three_amounts_pattern = r'([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$'
    three_match = re.search(three_amounts_pattern, rest)
    
    if three_match:
        description = rest[:three_match.start()].strip()
        withdrawal = Decimal(three_match.group(1).replace(',', ''))
        deposit = Decimal(three_match.group(2).replace(',', ''))
        balance = Decimal(three_match.group(3).replace(',', ''))
        
        date = datetime(current_year, month, day).date()
        return (date, description, withdrawal, deposit, balance)
    
    return None

# Parse all text files
text_files = sorted(glob.glob('l:\\limo\\data\\2014_cibc3_page*.txt'))

print(f"Found {len(text_files)} text files to parse")

transactions = []

for text_file in text_files:
    print(f"Parsing: {text_file}")
    
    with open(text_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.split('\n')
    
    for line in lines:
        result = parse_transaction_line(line)
        if result:
            transactions.append(result)

# Sort by date
transactions.sort(key=lambda t: t[0])

# Calculate debit/credit from withdrawal/deposit
final_transactions = []
for date, description, withdrawal, deposit, balance in transactions:
    debit = withdrawal if withdrawal > 0 else Decimal('0')
    credit = deposit if deposit > 0 else Decimal('0')
    final_transactions.append((date, description, debit, credit, balance))

# Write to CSV
csv_file = 'l:\\limo\\data\\2014_cibc3_transactions.csv'
with open(csv_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f, delimiter='|')
    for date, description, debit, credit, balance in final_transactions:
        writer.writerow([date.strftime('%b. %d, %Y'), description,
                        f'{debit:.2f}' if debit > 0 else '',
                        f'{credit:.2f}' if credit > 0 else '',
                        f'{balance:.2f}'])

print(f"\nParsed {len(final_transactions)} transactions")
print(f"Wrote {len(final_transactions)} transactions to: {csv_file}")

# Show sample
print("\nSample transactions:")
for date, description, debit, credit, balance in final_transactions[:10]:
    debit_str = f'D:${debit:>8.2f}' if debit > 0 else 'D:         '
    credit_str = f'C:${credit:>8.2f}' if credit > 0 else 'C:         '
    print(f"  {date} {description[:50]:50s} {debit_str} {credit_str} Bal:${balance:,.2f}")

if len(final_transactions) > 10:
    print(f"  ... and {len(final_transactions) - 10} more")
