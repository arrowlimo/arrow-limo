import pdfplumber
from pathlib import Path

# Extract all pages from 2014 CIBC 1615 PDF
output_dir = Path("L:\\limo\\data")

with pdfplumber.open("L:\\limo\\pdf\\2014\\2014 cibc 1615.pdf") as pdf:
    print(f"Extracting {len(pdf.pages)} pages from CIBC 1615 statement...")
    
    for i, page in enumerate(pdf.pages):
        text = page.extract_text()
        
        output_path = output_dir / f"2014_cibc_1615_page{i+1}.txt"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        print(f"  Extracted page {i+1}")

print(f"\nExtracted all pages to l:\\limo\\data\\2014_cibc_1615_page*.txt")
