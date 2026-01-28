#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Extract transactions from 2014 CIBC PDF statement.
Parse text and output to CSV format for import.
"""
import pdfplumber
import re
from datetime import datetime

pdf_path = r'L:\limo\pdf\2014\2014 cibc2 8362.pdf'

print(f"Extracting text from: {pdf_path}")
print("=" * 70)

transactions = []

with pdfplumber.open(pdf_path) as pdf:
    print(f"PDF has {len(pdf.pages)} pages")
    
    for page_num, page in enumerate(pdf.pages, 1):
        text = page.extract_text()
        if text:
            print(f"\nPage {page_num} preview (first 500 chars):")
            print(text[:500])
            print("...")
            
            # Save full text for manual review if needed
            with open(f'l:\\limo\\data\\2014_cibc2_page{page_num}.txt', 'w', encoding='utf-8') as f:
                f.write(text)
            print(f"Saved to: l:\\limo\\data\\2014_cibc2_page{page_num}.txt")

print("\n" + "=" * 70)
print("Text extraction complete. Review .txt files to identify transaction patterns.")
print("Next: Parse transaction lines and convert to CSV format.")
