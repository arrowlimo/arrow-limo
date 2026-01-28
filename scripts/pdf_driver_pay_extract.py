import os
import re
from pathlib import Path
import pdfplumber
import pandas as pd

def extract_driver_pay_from_pdf(pdf_path):
    records = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            # Heuristic: look for lines with driver names and pay amounts
            for line in text.splitlines():
                # Example pattern: Name ... $Amount
                match = re.search(r'(\b[A-Z][a-z]+,? [A-Z][a-z]+\b).*?(\$?\d{1,3}(,\d{3})*(\.\d{2})?)', line)
                if match:
                    driver = match.group(1)
                    amount = match.group(2).replace('$','').replace(',','')
                    try:
                        amount = float(amount)
                    except Exception:
                        continue
                    records.append({'driver_name': driver, 'amount': amount, 'source_line': line})
    return pd.DataFrame(records)

if __name__ == '__main__':
    # Example usage: scan all PDFs in quickbooks folders
    QB_DIRS = [
        r"L:\\limo\\quickbooks",
        r"L:\\limo\\quickbooks\\New folder",
    ]
    for base in QB_DIRS:
        for path in Path(base).rglob('*.pdf'):
            print(f"Extracting from {path}...")
            df = extract_driver_pay_from_pdf(path)
            print(df.head())
