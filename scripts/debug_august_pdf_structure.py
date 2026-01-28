#!/usr/bin/env python3
"""
Debug script to understand August 2012 PDF table structure.
Shows exactly what pdfplumber extracts.
"""

import pdfplumber
from pathlib import Path

pdf_path = Path(r'L:\limo\pdf\August 2012 - Payroll Summary_ocred (1).pdf')

print(f"Analyzing: {pdf_path.name}\n")

with pdfplumber.open(pdf_path) as pdf:
    for page_num, page in enumerate(pdf.pages, 1):
        print(f"=== PAGE {page_num} ===\n")
        
        tables = page.extract_tables()
        print(f"Found {len(tables)} table(s)\n")
        
        for table_num, table in enumerate(tables, 1):
            print(f"--- TABLE {table_num} ---")
            print(f"Dimensions: {len(table)} rows x {len(table[0]) if table else 0} columns\n")
            
            # Show ALL rows
            for row_num, row in enumerate(table):
                print(f"Row {row_num}: {row}")
            
            print()  # Blank line between tables
