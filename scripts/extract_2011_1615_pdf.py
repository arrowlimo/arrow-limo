"""Extract text from 2011 CIBC 1615 PDF using pdfplumber."""
import pdfplumber
import json

pdf_path = r"L:\limo\pdf\2011\2011 cibc 1615 ocr.pdf"

try:
    with pdfplumber.open(pdf_path) as pdf:
        print(f"PDF has {len(pdf.pages)} pages")
        print("=" * 80)
        
        # Extract all text
        for page_num, page in enumerate(pdf.pages):
            print(f"\nPAGE {page_num + 1}:")
            print("-" * 80)
            text = page.extract_text()
            if text:
                print(text)
            else:
                print("(No text extracted - likely image-based PDF)")
            
            # Try to extract tables
            tables = page.extract_tables()
            if tables:
                print(f"\nTables found on page {page_num + 1}: {len(tables)}")
                for table_num, table in enumerate(tables):
                    print(f"\nTable {table_num + 1}:")
                    for row in table:
                        print(" | ".join(str(cell) if cell else "" for cell in row))
        
except Exception as e:
    print(f"Error reading PDF: {e}")
    import traceback
    traceback.print_exc()
