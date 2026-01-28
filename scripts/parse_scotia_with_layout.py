"""
Scotia Bank 2012 PDF Parser using Layout-Aware Text Extraction

This approach uses pdfplumber's character-level extraction to preserve
column positions and properly separate fields.
"""
import pdfplumber
import re
from decimal import Decimal
from datetime import datetime
import csv

def fix_ocr_amount(text):
    """Fix OCR corruption in amounts."""
    if not text:
        return None
    
    text = text.replace(' ', '').replace('\t', '').replace('\n', '')
    text = text.replace('!', '.').replace(':', '.').replace('i', '.')
    text = text.replace('b', '0').replace('D', '0').replace('O', '0')
    text = text.replace('l', '1').replace('I', '1').replace('|', '1')
    text = text.replace('r', '').replace('V', '').replace('v', '').replace('..', '.')
    text = text.replace('F', '').replace('f', '').replace('°', '0').replace('�', '').replace('o', '0')
    text = text.replace('j', '').replace('C', '').replace('c', '').replace(',', '')
    
    text = re.sub(r'[^0-9.]', '', text)
    
    if not text or text == '.':
        return None
    
    parts = text.split('.')
    if len(parts) > 2:
        dollars = ''.join(parts[:-1])
        cents = parts[-1]
        text = f"{dollars}.{cents}"
    
    if '.' in text:
        parts = text.split('.')
        dollars = parts[0] if parts[0] else '0'
        cents = parts[1][:2] if len(parts) > 1 else '00'
        text = f"{dollars}.{cents.zfill(2)}"
    else:
        if len(text) >= 3:
            text = f"{text[:-2]}.{text[-2:]}"
        elif len(text) == 2:
            text = f"0.{text}"
        elif len(text) == 1:
            text = f"0.0{text}"
        else:
            return None
    
    try:
        return Decimal(text)
    except:
        return None

def extract_with_layout(pdf_path, sample_pages=5):
    """Extract text from first few pages with layout analysis."""
    print(f"Opening PDF: {pdf_path}")
    print(f"Analyzing layout from first {sample_pages} pages...")
    
    with pdfplumber.open(pdf_path) as pdf:
        print(f"Total pages: {len(pdf.pages)}")
        
        for page_num in range(min(sample_pages, len(pdf.pages))):
            page = pdf.pages[page_num]
            
            print(f"\n{'='*100}")
            print(f"PAGE {page_num + 1} - Layout Analysis")
            print('='*100)
            
            # Extract with layout preservation
            text = page.extract_text(layout=True)
            
            if text:
                lines = text.split('\n')
                print(f"Total lines: {len(lines)}")
                
                # Show first 30 lines with line numbers
                for i, line in enumerate(lines[:30], 1):
                    print(f"{i:3d}: {repr(line)}")
            else:
                print("(No text extracted)")
            
            # Also try to extract tables with settings
            print(f"\n--- Table Extraction Attempt ---")
            tables = page.extract_tables({
                'vertical_strategy': 'text',
                'horizontal_strategy': 'text',
                'snap_tolerance': 3,
            })
            
            if tables:
                print(f"Found {len(tables)} tables")
                for ti, table in enumerate(tables, 1):
                    print(f"\nTable {ti}: {len(table)} rows")
                    for ri, row in enumerate(table[:5], 1):  # First 5 rows
                        print(f"  Row {ri}: {row}")
            else:
                print("No tables found")

if __name__ == '__main__':
    pdf_path = r'L:\limo\pdf\2012\2012 scotiabank statements all.pdf'
    
    print("="*100)
    print("SCOTIA BANK 2012 PDF LAYOUT ANALYZER")
    print("="*100)
    
    extract_with_layout(pdf_path, sample_pages=5)
    
    print("\n" + "="*100)
    print("ANALYSIS COMPLETE")
    print("="*100)
    print("\nNext steps:")
    print("1. Review the layout to identify column positions")
    print("2. Build column-position-based parser")
    print("3. Extract all transactions with proper field separation")
