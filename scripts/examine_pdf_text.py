#!/usr/bin/env python3
"""
Examine raw text from OCR'd PDFs to understand format.
"""

import pdfplumber
import os

def examine_pdf_text(pdf_path, max_pages=3):
    """Extract and display raw text from first few pages."""
    
    print(f"\n{'='*80}")
    print(f"📄 {os.path.basename(pdf_path)}")
    print(f"{'='*80}")
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"Total pages: {len(pdf.pages)}")
            
            for page_num in range(min(max_pages, len(pdf.pages))):
                page = pdf.pages[page_num]
                text = page.extract_text()
                
                print(f"\n--- PAGE {page_num + 1} ---")
                if text:
                    # Show first 2000 characters
                    print(text[:2000])
                    print(f"\n... (showing first 2000 chars of {len(text)} total)")
                else:
                    print("(No text extracted)")
                
                # Try extracting tables
                tables = page.extract_tables()
                if tables:
                    print(f"\n📊 Found {len(tables)} table(s) on this page")
                    for i, table in enumerate(tables[:2]):  # Show first 2 tables
                        print(f"\nTable {i+1}:")
                        for row in table[:5]:  # Show first 5 rows
                            print(row)
    
    except Exception as e:
        print(f"[WARN]  Error reading PDF: {e}")

if __name__ == '__main__':
    pdf_files = [
        r"L:\limo\CIBC UPLOADS\2012cibc banking jan-mar_ocred.pdf",
    ]
    
    for pdf_file in pdf_files:
        if os.path.exists(pdf_file):
            examine_pdf_text(pdf_file, max_pages=2)
        else:
            print(f"[WARN]  File not found: {pdf_file}")
