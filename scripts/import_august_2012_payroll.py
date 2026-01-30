#!/usr/bin/env python3
"""
Parse August 2012 payroll summary with correct structure understanding.
Employee names are in page text, amounts are in table columns.
"""

import pdfplumber
import re
from pathlib import Path
from decimal import Decimal
import psycopg2
from datetime import date

def clean_amount(text):
    """Convert text to decimal, handling parentheses as negative."""
    if not text or text == '-' or text == '':
        return Decimal('0.00')
    # Remove spaces, commas
    text = str(text).replace(' ', '').replace(',', '')
    # Handle parentheses as negative
    if text.startswith('(') and text.endswith(')'):
        text = '-' + text[1:-1]
    try:
        return Decimal(text)
    except:
        return Decimal('0.00')

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def parse_august_2012():
    """Parse August 2012 PDF and extract employee payroll data."""
    
    pdf_path = Path(r'L:\limo\pdf\August 2012 - Payroll Summary_ocred (1).pdf')
    
    print(f"Processing: {pdf_path.name}\n")
    
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        
        # Extract all text to find employee names
        text = page.extract_text()
        
        # Extract tables for amounts
        tables = page.extract_tables()
        
        # TABLE 2 has the financial data we need (Row 7 is Total Gross Pay)
        # Columns 2-13 are the employee amounts (column 1 is row labels)
        financial_table = tables[1]  # Second table (index 1)
        
        # Find the Total Gross Pay row
        gross_pay_row = None
        for row in financial_table:
            if row[0] and 'Total Gross Pay' in row[0]:
                gross_pay_row = row[1:-1]  # Skip first column (label) and last column (total)
                break
        
        print(f"Total Gross Pay row found: {len(gross_pay_row)} employee columns")
        print(f"Amounts: {gross_pay_row}\n")
        
        # TABLE 3 has tax withholding data
        tax_table = tables[2]  # Third table (index 2)
        
        # Extract tax rows (Table 3 has labels in column 1, not column 0)
        tax_rows = {}
        for row in tax_table:
            # Check column 0 OR column 1 for labels
            label = None
            if row[0]:
                label = str(row[0]).strip()
            elif row[1]:
                label = str(row[1]).strip()
            
            if not label:
                continue
            
            # Data starts at column 2, ends before last column (total)
            if 'Federal Income Tax' in label:
                tax_rows['tax'] = row[2:-1]
            elif 'CPP - Employee' in label:
                tax_rows['cpp'] = row[2:-1]
            elif 'EI - Employee' in label:
                tax_rows['ei'] = row[2:-1]
            elif 'CRA Payroll - Net Pay' in label or 'Net Pay' in label:
                tax_rows['net'] = row[2:-1]
        
        print("Tax data rows found:", list(tax_rows.keys()))
        if 'tax' in tax_rows:
            print(f"Tax amounts (first 3): {tax_rows['tax'][:3]}")
        if 'net' in tax_rows:
            print(f"Net amounts (first 3): {tax_rows['net'][:3]}")
        
        # Now we need to match this to employee names
        # From the PDF text and our verification, we know the 11 employees are:
        # (in column order based on the PDF layout)
        # First column in data arrays is None/empty, then employee data starts
        employee_names = [
            'Angel Escobar',      # Data column 1 ($1,455.50)
            'Chantal Thomas',     # Data column 2 ($292.50)
            'Dale Menard',        # Data column 3 ($1,434.57)
            'Doug Redmond',       # Data column 4 ($2,999.62) - VERIFIED FROM PAYSTUB
            'Dustan Townsend',    # Data column 5 ($285.00) - VERIFIED FROM PAYSTUB
            'Jeannie Shillington',# Data column 6 ($1,986.00)
            'Jesse Gordon',       # Data column 7 ($97.50)
            'Michael Richard',    # Data column 8 ($2,689.67) - VERIFIED FROM PAYSTUB
            'Paul Mansell',       # Data column 9 ($1,202.64)
            'Zak Keller',         # Data column 10 ($2,233.09)
            'Gordon Deans'        # Data column 11 ($97.50)
        ]
        
        # Verify our total matches
        expected_total = Decimal('14773.59')
        calculated_total = sum(clean_amount(amt) for amt in gross_pay_row if amt)
        print(f"\nExpected total: ${expected_total:,.2f}")
        print(f"Calculated total: ${calculated_total:,.2f}")
        print(f"Match: {abs(expected_total - calculated_total) < Decimal('0.10')}")
        
        # Build employee records
        # Skip first data element (None), then map to employee names
        employees = []
        for idx, name in enumerate(employee_names):
            # Data arrays start with None, so employee 0 is at index 1
            data_idx = idx + 1
            
            emp = {
                'name': name,
                'year': 2012,
                'month': 8,
                'gross': clean_amount(gross_pay_row[data_idx]) if data_idx < len(gross_pay_row) else Decimal('0.00'),
                'tax': abs(clean_amount(tax_rows['tax'][data_idx])) if 'tax' in tax_rows and data_idx < len(tax_rows['tax']) else Decimal('0.00'),
                'cpp': abs(clean_amount(tax_rows['cpp'][data_idx])) if 'cpp' in tax_rows and data_idx < len(tax_rows['cpp']) else Decimal('0.00'),
                'ei': abs(clean_amount(tax_rows['ei'][data_idx])) if 'ei' in tax_rows and data_idx < len(tax_rows['ei']) else Decimal('0.00'),
                'net': clean_amount(tax_rows['net'][data_idx]) if 'net' in tax_rows and data_idx < len(tax_rows['net']) else Decimal('0.00'),
            }
            
            # Skip if no gross pay (might be extra column)
            if emp['gross'] > 0:
                employees.append(emp)
                print(f"\n{name}:")
                print(f"  Gross: ${emp['gross']:,.2f}")
                print(f"  Tax: ${emp['tax']:,.2f}")
                print(f"  CPP: ${emp['cpp']:,.2f}")
                print(f"  EI: ${emp['ei']:,.2f}")
                print(f"  Net: ${emp['net']:,.2f}")
        
        return employees

def import_to_database(employees, dry_run=True):
    """Import employee payroll data to database."""
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Map employee names to driver IDs
        name_to_driver_id = {
            'Angel Escobar': 'Dr01',
            'Chantal Thomas': 'Dr04',
            'Dale Menard': 'Dr05',
            'Doug Redmond': 'Dr09',
            'Dustan Townsend': 'Dr10',
            'Jeannie Shillington': 'Dr14',
            'Jesse Gordon': 'Dr15',
            'Michael Richard': 'Dr26',
            'Paul Mansell': 'Dr34',
            'Zak Keller': 'Dr47',
            'Gordon Deans': 'Dr12'
        }
        
        print("\n" + "="*60)
        print("IMPORT TO DATABASE")
        print("="*60)
        print(f"Mode: {'DRY RUN' if dry_run else 'APPLYING CHANGES'}\n")
        
        for emp in employees:
            driver_id = name_to_driver_id.get(emp['name'])
            if not driver_id:
                print(f"[WARN] No driver_id mapping for {emp['name']}")
                continue
            
            pay_date = date(emp['year'], emp['month'], 31)  # Last day of month
            
            if dry_run:
                print(f"Would insert: {emp['name']} ({driver_id}) - ${emp['gross']:,.2f} gross, ${emp['net']:,.2f} net")
            else:
                cur.execute("""
                    INSERT INTO driver_payroll (
                        driver_id, year, month, pay_date,
                        gross_pay, cpp, ei, tax, net_pay,
                        source, imported_at
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, CURRENT_TIMESTAMP
                    )
                    RETURNING id
                """, (
                    driver_id, emp['year'], emp['month'], pay_date,
                    emp['gross'], emp['cpp'], emp['ei'], emp['tax'], emp['net'],
                    'August 2012 Monthly Payroll Summary PDF'
                ))
                
                new_id = cur.fetchone()[0]
                print(f"✓ Inserted: {emp['name']} ({driver_id}) - ID {new_id}")
        
        if not dry_run:
            conn.commit()
            print("\n✓ Changes committed to database")
        else:
            print("\n[WARN] DRY RUN - No changes made. Run with --apply to import.")
        
    finally:
        cur.close()
        conn.close()

def main():
    import sys
    
    employees = parse_august_2012()
    
    print(f"\n{'='*60}")
    print(f"EXTRACTED {len(employees)} EMPLOYEES")
    print(f"Total gross: ${sum(e['gross'] for e in employees):,.2f}")
    print(f"Total net: ${sum(e['net'] for e in employees):,.2f}")
    print(f"{'='*60}\n")
    
    # Import to database
    dry_run = '--apply' not in sys.argv
    import_to_database(employees, dry_run=dry_run)

if __name__ == '__main__':
    main()
