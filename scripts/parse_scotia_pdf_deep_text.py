"""
Extract deeper text from Scotia PDF to see transaction layout.
Sample pages 10, 20, 30 with more text (5000 chars each).
"""
import pdfplumber

pdf_path = r'L:\limo\pdf\2012\2012 scotiabank statements all.pdf'

print(f"Opening PDF: {pdf_path}")
print("Extracting deeper text samples...")

with pdfplumber.open(pdf_path) as pdf:
    print(f"\nTotal pages: {len(pdf.pages)}")
    
    # Sample pages 10, 20, 30 with more text
    sample_pages = [10, 20, 30]
    
    for page_num in sample_pages:
        if page_num <= len(pdf.pages):
            print(f"\n{'='*100}")
            print(f"PAGE {page_num} - First 5000 characters:")
            print('='*100)
            
            page = pdf.pages[page_num - 1]
            text = page.extract_text()
            
            if text:
                print(text[:5000])
            else:
                print("(No text extracted)")
