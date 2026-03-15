"""
Analyze the current state of Scotia PDF after OCR attempts.
Check text quality and orientation on multiple pages.
"""
import pdfplumber
import re

pdf_path = r'L:\limo\pdf\2012\2012 scotiabank statements all.pdf'

print(f"Analyzing: {pdf_path}\n")

with pdfplumber.open(pdf_path) as pdf:
    print(f"Total pages: {len(pdf.pages)}\n")
    
    # Sample pages throughout the document
    sample_pages = [0, 5, 10, 20, 30, 40, 50]
    
    for page_idx in sample_pages:
        if page_idx >= len(pdf.pages):
            continue
            
        page = pdf.pages[page_idx]
        text = page.extract_text()
        
        print(f"{'='*80}")
        print(f"PAGE {page_idx + 1}")
        print(f"{'='*80}")
        
        if not text:
            print("NO TEXT EXTRACTED\n")
            continue
        
        lines = text.split('\n')
        print(f"Total lines: {len(lines)}")
        
        # Check for transaction keywords
        transaction_lines = [l for l in lines if any(kw in l.upper() for kw in 
                           ['DEPOSIT', 'WITHDRAWAL', 'PURCHASE', 'CHQ', 'BALANCE'])]
        print(f"Transaction-like lines: {len(transaction_lines)}")
        
        # Check orientation (reversed text indicates rotation issues)
        reversed_text = ('knabaitocS' in text or 'TIDERC' in text or 'TISED' in text)
        print(f"Appears reversed: {reversed_text}")
        
        # Show first 10 lines
        print(f"\nFirst 10 lines:")
        for i, line in enumerate(lines[:10], 1):
            print(f"  {i:2d}: {line[:70]}")
        
        # Show sample transaction lines
        if transaction_lines:
            print(f"\nSample transaction lines (first 3):")
            for i, line in enumerate(transaction_lines[:3], 1):
                print(f"  {i}: {line[:80]}")
        
        print()
