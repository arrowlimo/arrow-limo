#!/usr/bin/env python3
"""
Scan 2012 CIBC and QuickBooks PDFs (OCR'd versions)
==================================================

Extracts text from all 2012 OCR'd PDF files:
- 2012 CIBC banking statements (3 files: jan-mar, apr-may, jun-dec)
- 2012 QuickBooks export (1 file)

Uses pdfplumber to extract text from OCR'd PDFs.

Saves extracted text to staging directory for further parsing.

Safe: Read-only PDF extraction.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("[FAIL] pdfplumber not found. Install: pip install pdfplumber")
    sys.exit(1)


PDF_FILES = [
    r"L:\limo\pdf\2012cibc banking jan-mar_ocred.pdf",
    r"L:\limo\pdf\2012cibc banking apr- may_ocred.pdf",
    r"L:\limo\pdf\2012cibc banking jun-dec_ocred.pdf",
    r"L:\limo\pdf\2012 quickbooks_ocred.pdf",
]

OUTPUT_DIR = r"L:\limo\staging\2012_pdf_extracts"


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def extract_pdf_text(pdf_path: str) -> tuple[str, dict]:
    """Extract text from PDF and return (text, metadata)"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page_num, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""
                text += f"\n{'='*80}\nPage {page_num}\n{'='*80}\n{page_text}\n"
            
            metadata = {
                "total_pages": len(pdf.pages),
                "file_size": os.path.getsize(pdf_path),
            }
            
            return text, metadata
    except Exception as e:
        return "", {"error": str(e)}


def main():
    print("=" * 80)
    print("2012 PDF EXTRACTION")
    print("=" * 80)
    print()
    
    ensure_dir(OUTPUT_DIR)
    
    for pdf_path in PDF_FILES:
        if not os.path.exists(pdf_path):
            print(f"[WARN]  File not found: {pdf_path}")
            continue
        
        filename = Path(pdf_path).stem
        print(f"\n📄 Processing: {filename}")
        print(f"   Path: {pdf_path}")
        
        text, metadata = extract_pdf_text(pdf_path)
        
        if metadata.get("error"):
            print(f"   [FAIL] Error: {metadata['error']}")
            continue
        
        # Save extracted text
        output_path = os.path.join(OUTPUT_DIR, f"{filename}.txt")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
        
        print(f"   [OK] Extracted {metadata['total_pages']} pages")
        print(f"   💾 Saved to: {output_path}")
        print(f"   📊 Text length: {len(text):,} characters")
    
    print("\n" + "=" * 80)
    print("EXTRACTION COMPLETE")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 80)


if __name__ == "__main__":
    main()
