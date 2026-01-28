#!/usr/bin/env python3
"""
Import October and November 2012 monthly payroll summaries.
These have a different structure from August - employee names are in Table 1.
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
    text = str(text).replace(' ', '').replace(',', '').replace('\n', ' ')
    if text.startswith('(') and text.endswith(')'):
        text = '-' + text[1:-1]
    try:
        return Decimal(text)
    except:
        return Decimal('0.00')

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def parse_oct_nov_summary(pdf_path):
    """Parse Oct/Nov 2012 format where employee names are in Table 1."""
    
    # Extract month/year from filename
    match = re.search(r'(October|November).*?(\d{4})', pdf_path.name, re.IGNORECASE)
    if not match:
        print(f"  [WARN] Could not extract month/year from {pdf_path.name}")
        return []
    
    month_name = match.group(1)
    year = int(match.group(2))
    month = {'october': 10, 'november': 11}[month_name.lower()]
    
    print(f"\n{'='*60}")
    print(f"Processing: {month_name} {year}")
    print(f"File: {pdf_path.name}")
    print(f"{'='*60}")
    
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        tables = page.extract_tables()
        
        if len(tables) < 4:
            print(f"  [WARN] Expected at least 4 tables, found {len(tables)}")
            return []
        
        # TABLE 1 has employee names
        names_table = tables[0]
        if not names_table or not names_table[0]:
            print(f"  [WARN] No employee names found in Table 1")
            return []
        
        employee_names = [name.strip().replace('\n', ' ') for name in names_table[0] if name and name != 'TOTAL']
        print(f"Found {len(employee_names)} employees: {', '.join(employee_names[:5])}...")
        
        # TABLE 3 has wages/gratuities/gross pay
        financial_table = tables[2]
        
        # Find Total Gross Pay row
        gross_pay_row = None
        for row in financial_table:
            if row[0] and 'Total Gross Pay' in str(row[0]):
                gross_pay_row = row[1:]  # Skip label column
                break
        
        if not gross_pay_row:
            print(f"  [WARN] Could not find Total Gross Pay row")
            # Try alternate search
            for row in financial_table:
                if any(cell and 'Gross' in str(cell) for cell in row if cell):
                    print(f"  Found row with 'Gross': {row}")
            return []
        
        # Remove TOTAL column (last one)
        gross_pay_row = gross_pay_row[:-1]
        
        # TABLE 4 has tax withholding
        tax_table = tables[3]
        
        # Extract tax rows
        tax_rows = {}
        for row in tax_table:
            # Check all columns for labels
            label = None
            for cell in row[:3]:
                if cell and isinstance(cell, str):
                    if 'Federal Income Tax' in cell or 'Income Tax' in cell:
                        label = 'tax'
                        break
                    elif 'CPP - Employee' in cell or 'CPP-Employee' in cell:
                        label = 'cpp'
                        break
                    elif 'EI - Employee' in cell or 'EI-Employee' in cell:
                        label = 'ei'
                        break
                    elif 'Net Pay' in cell:
                        label = 'net'
                        break
            
            if label:
                # Find where data starts (skip label columns)
                data_start = 0
                for i, cell in enumerate(row):
                    if cell and (cell.replace('.', '').replace(',', '').replace('-', '').replace('(', '').replace(')', '').replace(' ', '').isdigit() or cell == '-'):
                        data_start = i
                        break
                
                if data_start > 0:
                    tax_rows[label] = row[data_start:-1] if len(row) > data_start else []  # Exclude TOTAL
        
        print(f"Tax data rows: {list(tax_rows.keys())}")
        
        # Calculate total for verification
        calculated_total = sum(clean_amount(amt) for amt in gross_pay_row if amt)
        print(f"Calculated gross total: ${calculated_total:,.2f}")
        
        # Build employee records
        employees = []
        for idx, name in enumerate(employee_names):
            if idx >= len(gross_pay_row):
                print(f"  [WARN] No data for {name} (index {idx} beyond data array length)")
                continue
            
            emp = {
                'name': name,
                'year': year,
                'month': month,
                'gross': clean_amount(gross_pay_row[idx]),
                'tax': abs(clean_amount(tax_rows['tax'][idx])) if 'tax' in tax_rows and idx < len(tax_rows['tax']) else Decimal('0.00'),
                'cpp': abs(clean_amount(tax_rows['cpp'][idx])) if 'cpp' in tax_rows and idx < len(tax_rows['cpp']) else Decimal('0.00'),
                'ei': abs(clean_amount(tax_rows['ei'][idx])) if 'ei' in tax_rows and idx < len(tax_rows['ei']) else Decimal('0.00'),
                'net': clean_amount(tax_rows['net'][idx]) if 'net' in tax_rows and idx < len(tax_rows['net']) else Decimal('0.00'),
            }
            
            if emp['gross'] > 0:
                employees.append(emp)
                print(f"  ✓ {name}: Gross=${emp['gross']:,.2f}, Net=${emp['net']:,.2f}")
        
        print(f"\nExtracted {len(employees)} employees with gross pay")
        print(f"Total gross: ${sum(e['gross'] for e in employees):,.2f}")
        
        return employees

def import_to_database(all_employees, dry_run=True):
    """Import employee payroll data to database."""
    
    conn = get_db_connection()
    cur = conn.cursor()
    
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
        'Paul D Richard': 'Dr35',  # Different Paul
        'Zak Keller': 'Dr47',
        'Gordon Deans': 'Dr12',
        'Kevin Boulley': 'Dr17',
        'Logan Mosinsky': 'Dr21',
        'Kevin Kosik': 'Dr18',
        'Shawn Callin': 'Dr40',
    }
    
    try:
        print("\n" + "="*60)
        print("IMPORT TO DATABASE")
        print("="*60)
        print(f"Mode: {'DRY RUN' if dry_run else 'APPLYING CHANGES'}\n")
        
        inserted_count = 0
        skipped_count = 0
        
        for emp in all_employees:
            driver_id = name_to_driver_id.get(emp['name'])
            
            if not driver_id:
                print(f"[WARN] No driver_id mapping for {emp['name']}")
                skipped_count += 1
                continue
            
            pay_date = date(emp['year'], emp['month'], 28)
            
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
                    f'{emp["year"]}-{emp["month"]:02d} Monthly Payroll Summary PDF'
                ))
                
                new_id = cur.fetchone()[0]
                inserted_count += 1
                print(f"✓ Inserted: {emp['name']} ({driver_id}) - ID {new_id}")
        
        if not dry_run:
            conn.commit()
            print(f"\n✓ {inserted_count} records committed to database")
            if skipped_count > 0:
                print(f"[WARN] {skipped_count} records skipped (no driver_id mapping)")
        else:
            print(f"\n[WARN] DRY RUN - No changes made. Run with --apply to import.")
            if skipped_count > 0:
                print(f"[WARN] {skipped_count} records would be skipped (no driver_id mapping)")
        
    finally:
        cur.close()
        conn.close()

def main():
    import sys
    
    pdf_dir = Path(r'L:\limo\pdf')
    target_months = ['October', 'November']
    
    all_employees = []
    
    for month_name in target_months:
        # Find PDF for this month
        pdfs = list(pdf_dir.glob(f'*{month_name}*2012*Payroll*.pdf'))
        
        if not pdfs:
            print(f"\n[WARN] No PDF found for {month_name} 2012")
            continue
        
        # Use first PDF
        pdf_path = pdfs[0]
        employees = parse_oct_nov_summary(pdf_path)
        all_employees.extend(employees)
    
    print(f"\n{'='*60}")
    print(f"EXTRACTION SUMMARY")
    print(f"{'='*60}")
    print(f"Total employees extracted: {len(all_employees)}")
    print(f"Total gross pay: ${sum(e['gross'] for e in all_employees):,.2f}")
    print(f"Total net pay: ${sum(e['net'] for e in all_employees):,.2f}")
    print(f"{'='*60}\n")
    
    # Import
    dry_run = '--apply' not in sys.argv
    import_to_database(all_employees, dry_run=dry_run)

if __name__ == '__main__':
    main()
