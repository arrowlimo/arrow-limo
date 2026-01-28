#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Extract month summaries from May-Dec 2012 CIBC 1615 PDFs."""

import pdfplumber
import re

files_to_check = [
    (r'L:\limo\pdf\2012\2012cibc banking apr- may_ocred.pdf', ['May']),
    (r'L:\limo\pdf\2012\2012cibc banking jun-dec_ocred.pdf', ['June', 'July', 'August', 'September', 'October', 'November', 'December']),
]

for pdf_path, target_months in files_to_check:
    print(f"\n{'='*100}")
    print(f"CHECKING: {pdf_path.split(chr(92))[-1]}")
    print(f"{'='*100}")
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"Total pages: {len(pdf.pages)}\n")
            
            # Sample pages at intervals to find month boundaries
            for page_num in [0, 10, 20, 30, 40, 50, 60, 70, 80]:
                if page_num < len(pdf.pages):
                    page = pdf.pages[page_num]
                    text = page.extract_text()
                    
                    # Extract header line
                    lines = text.split('\n')
                    header = ' '.join(lines[:10])
                    
                    # Look for month and date range
                    if any(month in header.upper() for month in target_months):
                        print(f"Page {page_num+1:2d}: {header[:120]}...")
                        
                        # Try to extract month summary
                        if 'Account summary' in text:
                            lines = text.split('\n')
                            for i, line in enumerate(lines):
                                if 'Opening balance on' in line:
                                    print(f"  → OPENING BALANCE LINE: {line}")
                                if 'Closing balance on' in line:
                                    print(f"  → CLOSING BALANCE LINE: {line}")
                    else:
                        print(f"Page {page_num+1:2d}: {header[:100]}...")
            
            print(f"\n✅ File has {len(pdf.pages)} pages total")
            
    except Exception as e:
        print(f"❌ Error reading {pdf_path}: {e}")
