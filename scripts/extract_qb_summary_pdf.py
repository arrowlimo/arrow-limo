#!/usr/bin/env python3
"""
Extract QuickBooks Summary Data from PDF
========================================

Reads a PDF containing QuickBooks summary reports (e.g., bank reconciliation
summaries, transaction lists) and extracts text for parsing and cross-checking
against banking_transactions and receipts.

Usage:
  python -X utf8 scripts/extract_qb_summary_pdf.py --pdf "L:\limo\receipts\2012 quickbooks summarys.pdf" --output exports/qb/2012_qb_summary.txt

Requires:
  pip install pypdf2 or pdfplumber
"""
from __future__ import annotations

import os
import sys
import argparse

# Try importing PDF libraries (prefer pdfplumber, then pypdf2, then pypdf)
PDF_LIB = None
try:
    import pdfplumber
    PDF_LIB = 'pdfplumber'
except ImportError:
    try:
        from PyPDF2 import PdfReader  # type: ignore
        PDF_LIB = 'pypdf2'
    except ImportError:
        try:
            from pypdf import PdfReader as PyPdfReader  # type: ignore
            PDF_LIB = 'pypdf'
        except ImportError:
            print('[FAIL] No PDF library found. Install: pip install pdfplumber or pypdf')
            sys.exit(1)


def extract_with_pdfplumber(pdf_path: str) -> str:
    text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text.append(page.extract_text() or '')
    return '\n'.join(text)


def extract_with_pypdf2(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    text = []
    for page in reader.pages:
        text.append(page.extract_text() or '')
    return '\n'.join(text)

def extract_with_pypdf(pdf_path: str) -> str:
    reader = PyPdfReader(pdf_path)
    text = []
    for page in reader.pages:
        try:
            text.append(page.extract_text() or '')
        except Exception:
            continue
    return '\n'.join(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pdf', required=True, help='Path to QuickBooks summary PDF')
    ap.add_argument('--output', default=None, help='Output text file (default: stdout)')
    args = ap.parse_args()

    if not os.path.exists(args.pdf):
        print(f'[FAIL] PDF not found: {args.pdf}')
        return 1

    print(f'📄 Extracting text from: {args.pdf}')
    print(f'   Using library: {PDF_LIB}')

    try:
        if PDF_LIB == 'pdfplumber':
            text = extract_with_pdfplumber(args.pdf)
        elif PDF_LIB == 'pypdf2':
            text = extract_with_pypdf2(args.pdf)
        else:
            text = extract_with_pypdf(args.pdf)
    except Exception as e:
        print(f'[FAIL] Extraction failed: {e}')
        return 1

    if args.output:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f'[OK] Extracted {len(text)} characters to: {args.output}')
    else:
        print('--- BEGIN EXTRACTED TEXT ---')
        print(text)
        print('--- END EXTRACTED TEXT ---')

    return 0


if __name__ == '__main__':
    sys.exit(main())
