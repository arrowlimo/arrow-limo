#!/usr/bin/env python3
"""
Extract all unique transaction types from Scotia Bank reconciliation PDFs.
"""
import PyPDF2
import re
import glob
from collections import Counter

def extract_transaction_types():
    """Find all transaction type patterns in Scotia reconciliation PDFs."""
    files = glob.glob('l:/limo/pdf/2012/*scotia*reconciliation*.pdf')
    
    if not files:
        print("No Scotia Bank reconciliation PDFs found")
        return
    
    print(f"Scanning {len(files)} PDF files...\n")
    
    types = []
    
    for pdf_file in sorted(files):
        print(f"Reading: {pdf_file.split('/')[-1]}")
        try:
            reader = PyPDF2.PdfReader(open(pdf_file, 'rb'))
            for page in reader.pages:
                text = page.extract_text()
                # Pattern: TYPE first, then date
                # Looking for lines like: Cheque 07/12/2012 dd Centex X -36.01
                # or: Bill Pm! -Cheque 07/13/2012 4 Eries Auto Repair X -840.95
                for line in text.split('\n'):
                    # Match transaction type at start followed by date
                    match = re.match(r'^([A-Za-z][A-Za-z\s\-!]+?)\s+\d{2}/\d{2}/\d{4}', line)
                    if match:
                        tx_type = match.group(1).strip()
                        # Clean up the type (remove extra spaces, normalize)
                        tx_type = ' '.join(tx_type.split())
                        types.append(tx_type)
        except Exception as e:
            print(f"  Error: {e}")
    
    print(f"\n{'='*60}")
    print("TRANSACTION TYPES FOUND")
    print(f"{'='*60}\n")
    
    type_counts = Counter(types)
    
    for tx_type, count in sorted(type_counts.items()):
        print(f"{tx_type:30s} : {count:4d} occurrences")
    
    print(f"\n{'='*60}")
    print(f"Total unique types: {len(type_counts)}")
    print(f"Total transactions: {sum(type_counts.values())}")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    extract_transaction_types()
