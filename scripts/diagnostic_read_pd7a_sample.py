"""Quick diagnostic to read a sample PD7A PDF and show its text"""
import pdfplumber
from pathlib import Path

pdf_path = Path(r"L:\limo\pdf\2012\pay\PDOC\Jul.2012 PD7A_ocred (1).pdf")

print(f"Analyzing: {pdf_path.name}\n")

with pdfplumber.open(pdf_path) as pdf:
    print(f"Total pages: {len(pdf.pages)}\n")
    for i, page in enumerate(pdf.pages[:2]):
        print(f"PAGE {i+1}")
        print("-" * 70)
        text = page.extract_text() or ""
        print(text[:2000])
        print("\n")
