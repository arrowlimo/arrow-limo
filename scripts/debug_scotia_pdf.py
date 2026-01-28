"""Debug script to see what's in the Scotia PDF."""
import pdfplumber

pdf_path = r"L:\limo\pdf\2012\2012 scotiabank statements all.pdf"

with pdfplumber.open(pdf_path) as pdf:
    # Check first few pages
    for page_num in [0, 1, 2]:
        page = pdf.pages[page_num]
        text = page.extract_text()
        
        print(f"\n{'='*80}")
        print(f"PAGE {page_num + 1}")
        print('='*80)
        print(text[:2000])  # First 2000 characters
        print("\n... (truncated)")
