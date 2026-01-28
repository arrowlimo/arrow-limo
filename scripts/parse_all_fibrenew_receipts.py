#!/usr/bin/env python3
"""
Parse all Fibrenew receipt PDFs to extract:
- Receipt dates
- Payment amounts
- Invoice numbers that were paid
- Running balance information

Cross-reference with statement to identify missing invoices.
"""
import os
import re
from pathlib import Path
import PyPDF2
from decimal import Decimal
from datetime import datetime

RECEIPTS_DIR = r'L:\limo\audit_records\fibrenew'

def parse_receipt_pdf(pdf_path):
    """Extract payment info from a Fibrenew receipt PDF."""
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
        
        # Extract date
        date_match = re.search(r'Date:\s*(\d{2}/\d{2}/\d{4})', text)
        receipt_date = date_match.group(1) if date_match else None
        
        # Extract amount credited
        amount_match = re.search(r'Amount Credited:\s*\$?([\d,]+\.?\d*)', text)
        amount = Decimal(amount_match.group(1).replace(',', '')) if amount_match else None
        
        # Extract invoice numbers from table
        invoice_numbers = re.findall(r'Invoice Number\s+(\d+)', text)
        
        # Alternative pattern - just numbers in invoice context
        if not invoice_numbers:
            invoice_numbers = re.findall(r'(?:Invoice|Inv|#)\s*#?\s*(\d{4,})', text)
        
        return {
            'file': os.path.basename(pdf_path),
            'date': receipt_date,
            'amount': amount,
            'invoice_numbers': invoice_numbers,
            'raw_text': text[:500]  # First 500 chars for debugging
        }
    except Exception as e:
        return {
            'file': os.path.basename(pdf_path),
            'error': str(e)
        }

def main():
    print("\n" + "="*100)
    print("FIBRENEW RECEIPT ANALYSIS")
    print("="*100)
    
    receipt_files = [f for f in os.listdir(RECEIPTS_DIR) if f.endswith('.pdf')]
    
    print(f"\n📁 Found {len(receipt_files)} PDF files")
    print("-" * 100)
    
    receipts = []
    total_payments = Decimal('0')
    all_invoice_numbers = set()
    
    for filename in sorted(receipt_files):
        filepath = os.path.join(RECEIPTS_DIR, filename)
        receipt_data = parse_receipt_pdf(filepath)
        receipts.append(receipt_data)
        
        if 'error' not in receipt_data:
            print(f"\n{receipt_data['file']}")
            print(f"  Date: {receipt_data['date']}")
            print(f"  Amount: ${receipt_data['amount']:,.2f}" if receipt_data['amount'] else "  Amount: Not found")
            print(f"  Invoices: {', '.join(receipt_data['invoice_numbers']) if receipt_data['invoice_numbers'] else 'None found'}")
            
            if receipt_data['amount']:
                total_payments += receipt_data['amount']
            
            if receipt_data['invoice_numbers']:
                all_invoice_numbers.update(receipt_data['invoice_numbers'])
        else:
            print(f"\n{receipt_data['file']}")
            print(f"  ❌ Error: {receipt_data['error']}")
    
    print("\n" + "="*100)
    print("SUMMARY")
    print("="*100)
    print(f"\nTotal receipts processed: {len(receipts)}")
    print(f"Total payment amount: ${total_payments:,.2f}")
    print(f"Unique invoice numbers found: {len(all_invoice_numbers)}")
    
    if all_invoice_numbers:
        print("\n📋 All invoice numbers from receipts:")
        for inv in sorted(all_invoice_numbers, key=int):
            print(f"  #{inv}")
    
    print("\n" + "="*100)

if __name__ == '__main__':
    main()
