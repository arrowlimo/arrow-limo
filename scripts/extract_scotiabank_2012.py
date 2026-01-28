#!/usr/bin/env python3
"""
Extract Scotiabank 2012 Documents
- Extract OCR text from Scotiabank PDFs
- Save to staging for parsing

Safe: Read-only extraction. Outputs text to staging/2012_pdf_extracts/
"""
from pathlib import Path
import pdfplumber

INPUT_FILES = [
    Path(r"L:\limo\pdf\2012 quickbooks scotiabank_ocred.pdf"),
    Path(r"L:\limo\pdf\2012 scotia bank statements_ocred.pdf"),
]
OUTPUT_DIR = Path(r"L:\limo\staging\2012_pdf_extracts")


def extract_text(pdf_path: Path) -> str:
    """Extract all text from PDF."""
    with pdfplumber.open(pdf_path) as pdf:
        pages = []
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return '\n\n--- PAGE BREAK ---\n\n'.join(pages)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    for pdf_path in INPUT_FILES:
        if not pdf_path.exists():
            print(f"SKIP: {pdf_path} (not found)")
            continue
        
        print(f"Extracting: {pdf_path.name}")
        text = extract_text(pdf_path)
        
        # Save with _ocred.txt suffix
        out_name = pdf_path.stem + '_ocred.txt'
        out_path = OUTPUT_DIR / out_name
        
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        print(f"  → {out_path}")
        print(f"  Extracted {len(text)} characters")
    
    print("\nExtraction complete.")


if __name__ == '__main__':
    main()
