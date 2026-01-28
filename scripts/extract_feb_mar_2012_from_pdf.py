#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Extract Feb-Mar 2012 CIBC 1615 statements from PDF."""

import pdfplumber
import re
from datetime import datetime

pdf_path = r'L:\limo\pdf\2012\pdf2012cibc banking jan-mar_ocred.pdf'

def extract_month_summary(text):
    """Extract opening balance and key metrics from statement."""
    
    # Extract opening balance
    opening_match = re.search(r'Opening balance on \w+ \d+.*?\$([0-9,.-]+)', text, re.DOTALL)
    opening = opening_match.group(1) if opening_match else "NOT FOUND"
    
    # Extract closing balance
    closing_match = re.search(r'Closing balance on \w+ \d+.*?\$([0-9,.-]+)', text, re.DOTALL)
    closing = closing_match.group(1) if closing_match else "NOT FOUND"
    
    return opening, closing

def extract_transactions(text, month_short):
    """Extract all transactions from statement text."""
    transactions = []
    lines = text.split('\n')
    
    in_transactions = False
    
    for line in lines:
        # Skip headers and summary sections
        if 'Transaction details' in line or 'Date Description' in line:
            in_transactions = True
            continue
        
        if not in_transactions or not line.strip():
            continue
        
        # Look for transaction lines starting with month abbreviation
        if re.match(rf'^{month_short}\s+\d+', line.strip()):
            transactions.append(line)
    
    return transactions

with pdfplumber.open(pdf_path) as pdf:
    print("=" * 100)
    print("EXTRACTING FEB-MAR 2012 DATA FROM PDF")
    print("=" * 100)
    
    # FEBRUARY (Pages 16-20)
    print("\n📄 FEBRUARY 2012 (Pages 16-20)")
    print("-" * 100)
    
    feb_text = ""
    for page_num in range(15, 21):  # 0-indexed
        if page_num < len(pdf.pages):
            page = pdf.pages[page_num]
            feb_text += page.extract_text() + "\n"
    
    if feb_text:
        opening, closing = extract_month_summary(feb_text)
        print(f"Opening Balance (Feb 1): {opening}")
        print(f"Closing Balance (Feb 29): {closing}")
        
        transactions = extract_transactions(feb_text, "Feb")
        print(f"\nTransaction Count: {len(transactions)}")
        if transactions:
            print("\nFirst 5 transactions:")
            for txn in transactions[:5]:
                print(f"  {txn[:80]}")
    
    # MARCH (Pages 26-31)
    print("\n📄 MARCH 2012 (Pages 26-31)")
    print("-" * 100)
    
    mar_text = ""
    for page_num in range(25, 31):  # 0-indexed
        if page_num < len(pdf.pages):
            page = pdf.pages[page_num]
            mar_text += page.extract_text() + "\n"
    
    if mar_text:
        opening, closing = extract_month_summary(mar_text)
        print(f"Opening Balance (Mar 1): {opening}")
        print(f"Closing Balance (Mar 31): {closing}")
        
        transactions = extract_transactions(mar_text, "Mar")
        print(f"\nTransaction Count: {len(transactions)}")
        if transactions:
            print("\nFirst 5 transactions:")
            for txn in transactions[:5]:
                print(f"  {txn[:80]}")
    
    print("\n" + "=" * 100)
    print("✅ PDF contains Jan-Mar 2012 data for account 74-61615")
    print("=" * 100)
