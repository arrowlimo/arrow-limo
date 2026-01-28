"""
Parse Scotia Bank 2012 statements PDF using text extraction with pattern matching.

Usage:
    python parse_scotia_pdf_text_2012.py
"""

import pdfplumber
import re
from decimal import Decimal
from datetime import datetime
import pandas as pd
import os


PDF_PATH = r"L:\limo\pdf\2012\2012 scotiabank statements all.pdf"


def main():
    if not os.path.exists(PDF_PATH):
        print(f"ERROR: PDF not found at {PDF_PATH}")
        return
    
    print(f"Opening PDF: {PDF_PATH}")
    print("Extracting text to analyze structure...\n")
    
    with pdfplumber.open(PDF_PATH) as pdf:
        print(f"Total pages: {len(pdf.pages)}\n")
        
        # Sample first few pages to understand structure
        for page_num in [1, 2, 3]:
            if page_num <= len(pdf.pages):
                page = pdf.pages[page_num - 1]
                text = page.extract_text()
                
                print(f"="*100)
                print(f"PAGE {page_num} - First 2000 characters:")
                print(f"="*100)
                print(text[:2000] if text else "(No text extracted)")
                print("\n")


if __name__ == '__main__':
    main()
