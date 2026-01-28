#!/usr/bin/env python3
"""Extract invoice details from Amazon PDFs"""
from pathlib import Path
from PyPDF2 import PdfReader
import re

pdf_path = Path(r"L:\limo\mbna amazon\aluminum led attachemtn kit.pdf")

try:
    pdf = PdfReader(str(pdf_path))
    page = pdf.pages[0]
    text = page.extract_text()
    print("Extracted text (first 1000 chars):")
    print("="*70)
    print(text[:1000] if text else "No text extracted")
except Exception as e:
    print(f"Error: {e}")
