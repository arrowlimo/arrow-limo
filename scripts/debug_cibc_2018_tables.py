"""
Extract CIBC 8362 2018 PDF - FLEXIBLE PARSER
Uses table extraction instead of regex for better accuracy.
"""

import sys
from pathlib import Path
from decimal import Decimal

try:
    import pdfplumber
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pdfplumber"])
    import pdfplumber

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl"])
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill

pdf_path = Path(r"L:\limo\pdf\2018\CIBC 8362 2018.pdf")
output_path = Path(r"L:\limo\reports\CIBC_8362_2018_extracted.xlsx")

print("EXTRACTING CIBC 8362 2018 PDF - TABLE EXTRACTION + BALANCE AUDIT")
print("=" * 80)

transactions = []
opening_balance = None

with pdfplumber.open(pdf_path) as pdf:
    print(f"PDF has {len(pdf.pages)} pages\n")
    
    for page_num, page in enumerate(pdf.pages, 1):
        # Try table extraction
        tables = page.extract_tables()
        if tables:
            print(f"Page {page_num}: Found {len(tables)} tables")
            for table_num, table in enumerate(tables):
                for row in table:
                    if row and len(row) >= 4:
                        print(f"  Row: {row[:4]}")  # Debug first 4 columns

print(f"\n✅ Extracted {len(transactions)} transactions (table method)")
print("Check console output above to see table structure.")
