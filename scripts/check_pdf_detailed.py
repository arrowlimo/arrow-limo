#!/usr/bin/env python
"""Extract more detailed PDF content to understand format"""

import pdfplumber

pdf_path = r"L:\limo\pdf\2012\2012 quickbooks cibc bank reconciliation detailed_ocred.pdf"

with pdfplumber.open(pdf_path) as pdf:
    print(f"=== PAGE 1 FULL TEXT (first 100 lines) ===")
    first_page = pdf.pages[0]
    text = first_page.extract_text()
    
    lines = text.split('\n')
    for i, line in enumerate(lines[:100]):
        if line.strip():  # Only show non-empty lines
            print(f"{i+1:3d}: {line}")
    
    print(f"\n=== TOTAL LINES ON PAGE 1: {len(lines)} ===")
    
    # Try page 2 as well
    if len(pdf.pages) > 1:
        print(f"\n=== PAGE 2 SAMPLE (first 50 lines) ===")
        page2 = pdf.pages[1]
        text2 = page2.extract_text()
        lines2 = text2.split('\n')
        for i, line in enumerate(lines2[:50]):
            if line.strip():
                print(f"{i+1:3d}: {line}")
