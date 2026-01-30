#!/usr/bin/env python3
"""
Import all available 2012 monthly payroll summaries (Aug, Sep, Oct, Nov).
Uses the same parsing logic validated for August 2012.
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
    text = str(text).replace(' ', '').replace(',', '')
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
        password='***REDACTED***'
    )

def parse_monthly_summary(pdf_path):
    """Parse monthly payroll summary PDF (works for Aug-Nov 2012 format)."""
    
    # Extract month/year from filename
    match = re.search(r'(August|September|October|November).*?(\d{4})', pdf_path.name, re.IGNORECASE)
    if not match:
        print(f"  [WARN] Could not extract month/year from {pdf_path.name}")
        return []
    
    month_name = match.group(1)
    year = int(match.group(2))
    month = {'august': 8, 'september': 9, 'october': 10, 'november': 11}[month_name.lower()]
    
    print(f"\n{'='*60}")
    print(f"Processing: {month_name} {year}")
    print(f"{'='*60}")
    
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        tables = page.extract_tables()
        
        if len(tables) < 3:
            print(f"  [WARN] Expected at least 3 tables, found {len(tables)}")
            return []
        
        # TABLE 2 (index 1) has financial data
        financial_table = tables[1]
        
        # Find Total Gross Pay row
        gross_pay_row = None
        for row in financial_table:
            if row[0] and 'Total Gross Pay' in row[0]:
                gross_pay_row = row[1:-1]  # Skip label and total
                break
        
        if not gross_pay_row:
            print(f"  [WARN] Could not find Total Gross Pay row")
            return []
        
        # TABLE 3 (index 2) has tax data
        tax_table = tables[2]
        
        # Extract tax rows
        tax_rows = {}
        for row in tax_table:
            label = None
            if row[0]:
                label = str(row[0]).strip()
            elif len(row) > 1 and row[1]:
                label = str(row[1]).strip()
            
            if not label:
                continue
            
            if 'Federal Income Tax' in label:
                tax_rows['tax'] = row[2:-1]
            elif 'CPP - Employee' in label:
                tax_rows['cpp'] = row[2:-1]
            elif 'EI - Employee' in label:
                tax_rows['ei'] = row[2:-1]
            elif 'Net Pay' in label:
                tax_rows['net'] = row[2:-1]
        
        # Calculate totals for verification
        calculated_total = sum(clean_amount(amt) for amt in gross_pay_row if amt)
        
        print(f"Found {len(gross_pay_row)} employee columns")
        print(f"Total gross pay: ${calculated_total:,.2f}")
        print(f"Tax data rows: {list(tax_rows.keys())}")
        
        # Extract employee names from page text (we'll need to look at the PDF to map)
        # For now, create generic entries and let user verify
        employees = []
        for idx, gross_amt in enumerate(gross_pay_row):
            if gross_amt is None or gross_amt == '' or clean_amount(gross_amt) == 0:
                continue
            
            # Skip first None column
            data_idx = idx
            
            emp = {
                'name': f'Employee_{idx}',  # Placeholder
                'year': year,
                'month': month,
                'gross': clean_amount(gross_amt),
                'tax': abs(clean_amount(tax_rows['tax'][data_idx])) if 'tax' in tax_rows and data_idx < len(tax_rows['tax']) else Decimal('0.00'),
                'cpp': abs(clean_amount(tax_rows['cpp'][data_idx])) if 'cpp' in tax_rows and data_idx < len(tax_rows['cpp']) else Decimal('0.00'),
                'ei': abs(clean_amount(tax_rows['ei'][data_idx])) if 'ei' in tax_rows and data_idx < len(tax_rows['ei']) else Decimal('0.00'),
                'net': clean_amount(tax_rows['net'][data_idx]) if 'net' in tax_rows and data_idx < len(tax_rows['net']) else Decimal('0.00'),
            }
            
            if emp['gross'] > 0:
                employees.append(emp)
        
        print(f"Extracted {len(employees)} employees")
        print(f"Sample: Gross=${employees[0]['gross']}, Net=${employees[0]['net']}" if employees else "No employees")
        
        return employees

def import_to_database(all_employees, dry_run=True):
    """Import all employee records to database."""
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        print("\n" + "="*60)
        print("IMPORT TO DATABASE")
        print("="*60)
        print(f"Mode: {'DRY RUN' if dry_run else 'APPLYING CHANGES'}\n")
        
        inserted_count = 0
        
        for emp in all_employees:
            pay_date = date(emp['year'], emp['month'], 28)  # Use 28th (safe for all months)
            
            # Create a generic driver ID for now (will need manual mapping later)
            driver_id = f"UNKNOWN_{emp['name']}"
            
            if dry_run:
                print(f"Would insert: {emp['year']}-{emp['month']:02d} {emp['name']} - ${emp['gross']:,.2f} gross")
            else:
                # For now, skip import if name is placeholder
                if emp['name'].startswith('Employee_'):
                    print(f"[WARN] Skipping {emp['name']} - needs manual name mapping")
                    continue
                
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
                print(f"✓ Inserted: {emp['name']} - ID {new_id}")
        
        if not dry_run:
            conn.commit()
            print(f"\n✓ {inserted_count} records committed to database")
        else:
            print("\n[WARN] DRY RUN - No changes made.")
        
    finally:
        cur.close()
        conn.close()

def main():
    import sys
    
    # Find all 2012 monthly summary PDFs (excluding Aug which is already done)
    pdf_dir = Path(r'L:\limo\pdf')
    target_months = ['September', 'October', 'November']
    
    all_employees = []
    
    for month_name in target_months:
        # Find PDF for this month
        pdfs = list(pdf_dir.glob(f'*{month_name}*2012*Payroll*.pdf'))
        
        if not pdfs:
            print(f"\n[WARN] No PDF found for {month_name} 2012")
            continue
        
        # Use first PDF if multiple found
        pdf_path = pdfs[0]
        employees = parse_monthly_summary(pdf_path)
        all_employees.extend(employees)
    
    print(f"\n{'='*60}")
    print(f"TOTAL EXTRACTED: {len(all_employees)} EMPLOYEES")
    print(f"Total gross: ${sum(e['gross'] for e in all_employees):,.2f}")
    print(f"{'='*60}\n")
    
    # Import (dry run by default)
    dry_run = '--apply' not in sys.argv
    import_to_database(all_employees, dry_run=dry_run)

if __name__ == '__main__':
    main()
