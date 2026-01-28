"""
Test the Adobe OCR'd Scotia Bank PDF to see if it has better text quality.
"""
import pdfplumber

pdf_path = r'L:\limo\pdf\2012\2012 scotia bank statements_ocred.pdf'

print(f"Opening OCR'd PDF: {pdf_path}")

try:
    with pdfplumber.open(pdf_path) as pdf:
        print(f"Total pages: {len(pdf.pages)}")
        
        # Test first 3 pages
        for page_num in [0, 1, 2]:
            if page_num < len(pdf.pages):
                print(f"\n{'='*100}")
                print(f"PAGE {page_num + 1} - First 2000 characters:")
                print('='*100)
                
                page = pdf.pages[page_num]
                text = page.extract_text()
                
                if text:
                    print(text[:2000])
                else:
                    print("(No text)")
                
                # Try table extraction
                print(f"\n--- Table Extraction ---")
                tables = page.extract_tables()
                if tables:
                    print(f"Found {len(tables)} tables")
                    if tables[0]:
                        print(f"First table has {len(tables[0])} rows")
                        print("First 3 rows:")
                        for row in tables[0][:3]:
                            print(f"  {row}")
                else:
                    print("No tables found")
        
except FileNotFoundError:
    print("ERROR: File not found!")
    print("Available OCR'd files:")
    import os
    import glob
    
    ocr_files = glob.glob(r'L:\limo\pdf\2012\*ocred.pdf')
    for f in ocr_files:
        print(f"  {os.path.basename(f)}")
