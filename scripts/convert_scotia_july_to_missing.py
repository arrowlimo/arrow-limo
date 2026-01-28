#!/usr/bin/env python3
"""Convert Scotia July screenshot rows to missing_banking_rows format."""

import csv
import sys
import hashlib
from datetime import datetime

def create_hash(account, date, description, debit, credit):
    """Create deterministic hash for transaction."""
    text = f"{account}|{date}|{description}|{debit:.2f}|{credit:.2f}"
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

def convert_file(input_file, output_file):
    """Convert screenshot rows to missing banking rows format."""
    with open(input_file, 'r', encoding='utf-8') as f_in:
        reader = csv.DictReader(f_in)
        
        missing_rows = []
        for row in reader:
            account = row['account_number']
            date = row['date']
            amount_str = row['amount'].replace(',', '')
            amount = float(amount_str) / 100.0  # Convert from cents
            side = row['side']
            description = row['description']
            
            debit = amount if side == 'debit' else 0.0
            credit = amount if side == 'credit' else 0.0
            
            source_hash = create_hash(account, date, description, debit, credit)
            
            missing_rows.append({
                'account_number': account,
                'transaction_date': date,
                'description': description,
                'amount': f"{amount:.2f}",
                'side': side,
                'notes': '',
                'source': 'scotia_statement_2012'
            })
    
    # Write to output file
    with open(output_file, 'w', encoding='utf-8', newline='') as f_out:
        if missing_rows:
            fieldnames = ['account_number', 'transaction_date', 'description', 
                         'amount', 'side', 'notes', 'source']
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(missing_rows)
    
    print(f"✓ Converted {len(missing_rows)} rows: {input_file} -> {output_file}")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python convert_scotia_july_to_missing.py input.csv output.csv")
        sys.exit(1)
    
    convert_file(sys.argv[1], sys.argv[2])
