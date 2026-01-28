#!/usr/bin/env python
"""
Summarize merchants from OCR'd Triangle Mastercard statements.
Parses purchases lines (two dates at start) and extracts merchant text.
Prints top merchant counts to help choose targets (fuel, maintenance, etc.).
"""

import re
from collections import Counter
from pathlib import Path
from datetime import datetime
import PyPDF2


def iter_purchase_lines(text: str):
    # Yield lines that look like purchases: "MMM DD MMM DD ... amount"
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    start_re = re.compile(r'^([A-Z][a-z]{3})\s+(\d{1,2})\s+([A-Z][a-z]{3})\s+(\d{1,2})\s+(.+)$')
    amount_tail_re = re.compile(r'(-?\d[\d,]*\.\d{2})\s*$')

    i = 0
    while i < len(lines):
        m = start_re.match(lines[i])
        if not m:
            i += 1
            continue

        full_line = lines[i]
        j = i + 1
        while not amount_tail_re.search(full_line) and j < len(lines):
            nxt = lines[j]
            full_line = f"{full_line} {nxt}"
            full_line = re.sub(r'(\d+)\.(\d)\s+(\d)(?!\d)', r'\1.\2\3', full_line)  # fix split decimals
            j += 1

        amt_m = amount_tail_re.search(full_line)
        if amt_m:
            yield full_line
        i = j


def extract_merchant(desc: str) -> str:
    # After two dates, merchant/location appears before province + amount
    # Try to remove leading dates
    lead_re = re.compile(r'^([A-Z][a-z]{3})\s+\d{1,2}\s+[A-Z][a-z]{3}\s+\d{1,2}\s+')
    desc = lead_re.sub('', desc)
    # Remove trailing amount and optional province
    desc = re.sub(r'(?:[A-Z]{2})?\s*-?\d[\d,]*\.\d{2}\s*$', '', desc)
    # Collapse whitespace
    desc = ' '.join(desc.split())
    return desc.upper()


def main():
    pdf_dir = Path('l:/limo/pdf')
    ocr_pdfs = sorted(pdf_dir.glob('*mastercard*_ocred.pdf'))
    counts = Counter()

    for pdf_path in ocr_pdfs:
        try:
            reader = PyPDF2.PdfReader(str(pdf_path))
            text = ''.join((pg.extract_text() or '') for pg in reader.pages)
        except Exception as e:
            print(f"Error reading {pdf_path.name}: {e}")
            continue

        for row in iter_purchase_lines(text):
            merchant = extract_merchant(row)
            counts[merchant] += 1

    print("Top merchants (by line count):")
    for merchant, cnt in counts.most_common(40):
        print(f"{cnt:4d}  {merchant}")


if __name__ == '__main__':
    main()
