"""Quick diagnostic to read a sample T4 PDF and show its structure"""
import pdfplumber
from pathlib import Path

# Use a 2012 T4
pdf_path = Path(r"L:\limo\pdf\2012\pay\PDOC\2012 - 31 T4's - Employer Copy_ocred.pdf")

print(f"Analyzing: {pdf_path.name}\n")
print("=" * 70)

try:
    with pdfplumber.open(pdf_path) as pdf:
        print(f"Total pages: {len(pdf.pages)}\n")
        
        # Show first 2 pages
        for i, page in enumerate(pdf.pages[:2]):
            print(f"PAGE {i+1}")
            print("-" * 70)
            text = page.extract_text()
            if text:
                # Show first 1500 chars
                print(text[:1500])
            else:
                print("(No text extracted)")
            print("\n")
except Exception as e:
    print(f"ERROR: {e}")
