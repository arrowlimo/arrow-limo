#!/usr/bin/env python3
"""
Extract all invoices from the Fibrenew statement PDF with dates and amounts.
"""
import PyPDF2
import re
from decimal import Decimal
from datetime import datetime

STATEMENT_PATH = r'L:\limo\audit_records\fibrenew\Statement from Fibrenew Central Alberta.pdf'

def parse_statement_pdf():
    """Extract all invoice records from statement."""
    with open(STATEMENT_PATH, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text()
    
    print("="*100)
    print("STATEMENT TEXT EXTRACTION")
    print("="*100)
    print(full_text[:3000])  # First 3000 chars
    print("\n...")
    print(full_text[-1000:])  # Last 1000 chars
    
    # Parse invoice lines  
    # Pattern: DATE  DESCRIPTION  AMOUNT  OPEN_AMOUNT
    invoice_pattern = r'(\d{2}/\d{2}/\d{4})\s+(Invoice #(\d+)[^$]*?)\s+(\d+(?:,\d{3})*\.\d{2})\s+(\d+(?:,\d{3})*\.\d{2})'
    
    matches = re.findall(invoice_pattern, full_text)
    
    print("\n" + "="*100)
    print(f"FOUND {len(matches)} INVOICE RECORDS")
    print("="*100)
    print(f"{'Date':<12} {'Inv #':<8} {'Amount':>12} {'Open Amount':>12}")
    print("-"*100)
    
    invoices = []
    for date_str, desc, inv_num, amount_str, open_amt_str in matches:
        amount = Decimal(amount_str.replace(',', ''))
        open_amt = Decimal(open_amt_str.replace(',', ''))
        
        # Parse date
        dt = datetime.strptime(date_str, '%d/%m/%Y').date()
        
        invoices.append({
            'date': dt,
            'invoice_num': inv_num,
            'amount': amount,
            'open_amount': open_amt,
            'description': desc
        })
        
        print(f"{date_str:<12} {inv_num:<8} ${amount:>10,.2f} ${open_amt:>10,.2f}")
    
    print("-"*100)
    print(f"Total: {len(invoices)} invoices")
    
    return invoices

if __name__ == '__main__':
    parse_statement_pdf()
