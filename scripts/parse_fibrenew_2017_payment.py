#!/usr/bin/env python3
"""
Parse 2017 Fibrenew payment receipt from fibrenew_0001.xlsx.

This file contains a payment receipt dated 03/26/2019 showing:
- Invoice 7598 (10/01/2017): $472.50 paid
- Invoice 7848 (11/29/2017): $227.50 paid
- Total payment: $700.00 (paid in cash)
"""

import pandas as pd
import re
from datetime import datetime

def parse_fibrenew_2017_payment():
    """Parse the 2017 Fibrenew payment receipt."""
    
    file_path = r'L:\limo\receipts\fibrenew_0001.xlsx'
    
    print("PARSING 2017 FIBRENEW PAYMENT RECEIPT")
    print("=" * 80)
    
    # Read Sheet1 (payment receipt)
    df = pd.read_excel(file_path, sheet_name='Sheet1', header=None)
    
    print("\nRaw Sheet1 content:")
    print(df.to_string())
    
    # Extract payment information
    payment_date = None
    payment_amount = None
    payment_method = None
    invoices_paid = []
    
    for idx, row in df.iterrows():
        row_str = ' '.join([str(x) for x in row if pd.notna(x)])
        
        # Extract payment date
        if 'Date Received' in row_str:
            date_match = re.search(r'(\d{2}/\d{2}/\d{4})', row_str)
            if date_match:
                payment_date = datetime.strptime(date_match.group(1), '%m/%d/%Y').date()
        
        # Extract payment amount
        if 'Payment Amount' in row_str:
            amount_match = re.search(r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)', row_str)
            if amount_match:
                payment_amount = float(amount_match.group(1).replace(',', ''))
        
        # Extract payment method
        if 'Payment Method' in row_str:
            if 'Cash' in row_str:
                payment_method = 'Cash'
            elif 'Cheque' in row_str:
                payment_method = 'Cheque'
        
        # Extract invoice details
        invoice_match = re.search(r'(\d{2}/\d{2}/\d{4})\s+(\d+|[\'"]?\w+)\s+-?\$(\d+(?:,\d{3})*(?:\.\d{2})?)', row_str)
        if invoice_match:
            inv_date = datetime.strptime(invoice_match.group(1), '%m/%d/%Y').date()
            inv_number = invoice_match.group(2)
            inv_amount = float(invoice_match.group(3).replace(',', ''))
            invoices_paid.append({
                'date': inv_date,
                'invoice_number': inv_number,
                'amount': inv_amount
            })
    
    print("\n" + "=" * 80)
    print("EXTRACTED PAYMENT INFORMATION:")
    print("=" * 80)
    print(f"Payment Date: {payment_date}")
    print(f"Payment Amount: ${payment_amount:,.2f}")
    print(f"Payment Method: {payment_method}")
    print(f"\nInvoices Paid ({len(invoices_paid)}):")
    
    total_invoices = 0
    for inv in invoices_paid:
        print(f"  {inv['date']} - Invoice #{inv['invoice_number']}: ${inv['amount']:,.2f}")
        total_invoices += inv['amount']
    
    print(f"\nTotal Invoices: ${total_invoices:,.2f}")
    print(f"Payment Amount: ${payment_amount:,.2f}")
    print(f"Match: {'✓' if abs(total_invoices - payment_amount) < 0.01 else '✗'}")
    
    return {
        'payment_date': payment_date,
        'payment_amount': payment_amount,
        'payment_method': payment_method,
        'invoices_paid': invoices_paid
    }

if __name__ == '__main__':
    result = parse_fibrenew_2017_payment()
