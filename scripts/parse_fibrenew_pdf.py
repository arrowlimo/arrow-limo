#!/usr/bin/env python3
"""
Parse fibrenew invoices.pdf to find any missing invoices from 2017-2018.
"""

import PyPDF2
import re
from datetime import datetime
from decimal import Decimal

PDF_FILE = r'L:\limo\pdf\2012\fibrenew invoices.pdf'

def extract_invoices_from_text(text):
    """Extract invoice data from PDF text."""
    invoices = []
    
    # Pattern: Invoice# Date followed by amount
    # Example: "8319 10/1/2018" ... "650.00"
    
    # Find invoice number and date lines
    invoice_pattern = re.compile(r'Invoice#\s+Date\s+(\d+)\s+(\d{1,2}/\d{1,2}/\d{4})', re.MULTILINE)
    
    for match in invoice_pattern.finditer(text):
        inv_num = match.group(1)
        date_str = match.group(2)
        
        try:
            inv_date = datetime.strptime(date_str, '%m/%d/%Y').date()
            # Extract amount from nearby text
            # Look ahead for amount pattern
            after_text = text[match.end():match.end()+500]
            amount_match = re.search(r'(\d+\.\d{2})', after_text)
            if amount_match:
                amount = Decimal(amount_match.group(1))
                invoices.append({
                    'invoice': inv_num,
                    'date': inv_date,
                    'amount': amount
                })
        except:
            pass
    
    # Also try alternative pattern from first page (aging report style)
    # Example: "05/01/2017 INV #7371. Due 05/01/2017. Orig. Amount $472.50."
    aging_pattern = re.compile(r'(\d{2}/\d{2}/\d{4})\s+INV\s+#(\d+).*?Amount\s+\$?([\d,]+\.\d{2})', re.MULTILINE)
    
    for match in aging_pattern.finditer(text):
        date_str = match.group(1)
        inv_num = match.group(2)
        amount_str = match.group(3).replace(',', '')
        
        try:
            inv_date = datetime.strptime(date_str, '%m/%d/%Y').date()
            amount = Decimal(amount_str)
            invoices.append({
                'invoice': inv_num,
                'date': inv_date,
                'amount': amount
            })
        except:
            pass
    
    return invoices

def main():
    print("="*80)
    print("PARSING FIBRENEW INVOICES PDF")
    print("="*80)
    
    with open(PDF_FILE, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        print(f"\nTotal pages: {len(reader.pages)}")
        
        all_invoices = []
        
        for page_num in range(len(reader.pages)):
            text = reader.pages[page_num].extract_text()
            invoices = extract_invoices_from_text(text)
            
            if invoices:
                print(f"\nPage {page_num + 1}: Found {len(invoices)} invoices")
                for inv in invoices:
                    print(f"  {inv['invoice']:6} | {inv['date']} | ${inv['amount']:>9,.2f}")
                
                all_invoices.extend(invoices)
        
        # Remove duplicates
        seen = {}
        unique_invoices = []
        for inv in all_invoices:
            key = (inv['invoice'], inv['date'])
            if key not in seen:
                unique_invoices.append(inv)
                seen[key] = True
        
        print(f"\n{'='*80}")
        print(f"SUMMARY")
        print(f"{'='*80}")
        print(f"\nTotal unique invoices found: {len(unique_invoices)}")
        print(f"Date range: {min(inv['date'] for inv in unique_invoices)} to {max(inv['date'] for inv in unique_invoices)}")
        print(f"Total amount: ${sum(inv['amount'] for inv in unique_invoices):,.2f}")
        
        # Group by year
        by_year = {}
        for inv in unique_invoices:
            year = inv['date'].year
            if year not in by_year:
                by_year[year] = []
            by_year[year].append(inv)
        
        print(f"\nInvoices by year:")
        for year in sorted(by_year.keys()):
            invs = by_year[year]
            total = sum(inv['amount'] for inv in invs)
            print(f"  {year}: {len(invs):2} invoices (${total:>10,.2f})")
        
        print(f"\n{'='*80}")
        print("ALL INVOICES (sorted by date):")
        print(f"{'='*80}")
        for inv in sorted(unique_invoices, key=lambda x: x['date']):
            print(f"{inv['invoice']:6} | {inv['date']} | ${inv['amount']:>9,.2f}")

if __name__ == '__main__':
    main()
