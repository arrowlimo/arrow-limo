#!/usr/bin/env python3
"""
Parse 2012 monthly payroll summary PDFs with transposed format.
Employees are in COLUMNS, not rows.
"""

import pdfplumber
import re
from pathlib import Path
from decimal import Decimal

def clean_amount(text):
    """Convert text to decimal, handling parentheses as negative."""
    if not text or text == '-':
        return Decimal('0.00')
    # Remove spaces, commas
    text = text.replace(' ', '').replace(',', '')
    # Handle parentheses as negative
    if text.startswith('(') and text.endswith(')'):
        text = '-' + text[1:-1]
    try:
        return Decimal(text)
    except:
        return Decimal('0.00')

def extract_employee_columns(pdf_path):
    """Extract employee data from transposed table format."""
    print(f"\nProcessing: {pdf_path.name}")
    
    # Extract month/year from filename
    match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December).*?(\d{4})', pdf_path.name, re.IGNORECASE)
    if match:
        month_name = match.group(1)
        year = int(match.group(2))
        month = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12
        }[month_name.lower()]
    else:
        print("  [WARN] Could not extract month/year from filename")
        return []
    
    employees = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            print(f"  Page {page_num}:")
            
            # Extract all tables
            tables = page.extract_tables()
            print(f"    Found {len(tables)} table(s)")
            
            if not tables:
                continue
            
            # Find the table with employee names in header
            # Look for table where first data row contains labels like "Hours - Wages", "Wages", "Gratuities"
            for table_num, table in enumerate(tables, 1):
                if len(table) < 2:
                    continue
                
                # First row should be employee names (columns)
                header_row = table[0]
                
                # Skip if this looks like a totals section
                if any(cell and 'Total' in str(cell) for cell in header_row if cell):
                    continue
                
                # Count non-empty cells in header (employee names)
                employee_names = [cell.strip() if cell else None for cell in header_row[1:]]  # Skip first column (row labels)
                employee_names = [name for name in employee_names if name and name != '']
                
                if len(employee_names) < 3:  # Need at least a few employees
                    continue
                
                print(f"    Table {table_num}: Found {len(employee_names)} employee columns")
                print(f"      Employees: {employee_names[:3]}... (showing first 3)")
                
                # Build dictionary of row label → values
                row_data = {}
                for row in table[1:]:  # Skip header
                    if not row or not row[0]:
                        continue
                    label = row[0].strip() if row[0] else ''
                    if label:
                        row_data[label] = row[1:]  # All employee columns
                
                # Key row labels we need to extract
                key_labels = {
                    'hours': ['Hours - Wages', 'Hours-Wages', 'Hours'],
                    'wages': ['Wages', 'Wage'],
                    'gratuities': ['Gratuities', 'Gratuity', 'Tips'],
                    'expenses': ['Expenses', 'Expense', 'Reimbursement'],
                    'gross': ['Gross', 'Gross Pay', 'Total Gross'],
                    'cpp': ['CPP - Employee', 'CPP-Employee', 'CPP'],
                    'ei': ['EI - Employee', 'EI-Employee', 'EI'],
                    'tax': ['Federal Income Tax', 'Income Tax', 'Tax'],
                    'net': ['Net', 'Net Pay', 'Net Amount']
                }
                
                # Find actual row labels in this table
                found_labels = {}
                for key, possible_labels in key_labels.items():
                    for label in possible_labels:
                        if label in row_data:
                            found_labels[key] = label
                            break
                
                print(f"      Found row labels: {list(found_labels.keys())}")
                
                # Extract data for each employee
                for emp_idx, emp_name in enumerate(employee_names):
                    if not emp_name:
                        continue
                    
                    emp_data = {
                        'name': emp_name,
                        'month': month,
                        'year': year,
                        'hours': Decimal('0.00'),
                        'wages': Decimal('0.00'),
                        'gratuities': Decimal('0.00'),
                        'expenses': Decimal('0.00'),
                        'gross': Decimal('0.00'),
                        'cpp': Decimal('0.00'),
                        'ei': Decimal('0.00'),
                        'tax': Decimal('0.00'),
                        'net': Decimal('0.00')
                    }
                    
                    # Extract values from found row labels
                    for key, label in found_labels.items():
                        values = row_data[label]
                        if emp_idx < len(values) and values[emp_idx]:
                            emp_data[key] = clean_amount(values[emp_idx])
                    
                    # Only add if we have meaningful data (wages or gross > 0)
                    if emp_data['wages'] > 0 or emp_data['gross'] > 0:
                        employees.append(emp_data)
                        print(f"      ✓ {emp_name}: Gross=${emp_data['gross']}, Net=${emp_data['net']}")
                
                # If we found employees in this table, we're done with this page
                if employees:
                    break
    
    return employees

def main():
    # Find all monthly summary PDFs
    pdf_dir = Path(r'L:\limo\pdf')
    monthly_summaries = []
    
    for pdf_file in pdf_dir.rglob('*.pdf'):
        if 'Payroll Summary' in pdf_file.name or 'payroll summary' in pdf_file.name.lower():
            # Skip if it's a specific employee's paystub
            if any(name in pdf_file.name for name in ['Angel', 'Chantal', 'Dale', 'Doug', 'Dustan', 'Jeannie', 'Jesse', 'Michael', 'Paul', 'Zak']):
                continue
            monthly_summaries.append(pdf_file)
    
    print(f"Found {len(monthly_summaries)} monthly summary PDFs")
    
    all_employees = []
    
    for pdf_path in sorted(monthly_summaries):
        employees = extract_employee_columns(pdf_path)
        all_employees.extend(employees)
    
    print("\n" + "="*60)
    print("EXTRACTION SUMMARY")
    print("="*60)
    print(f"Total employees extracted: {len(all_employees)}")
    
    if all_employees:
        # Group by month
        by_month = {}
        for emp in all_employees:
            key = (emp['year'], emp['month'])
            if key not in by_month:
                by_month[key] = []
            by_month[key].append(emp)
        
        print("\nBy month:")
        for (year, month), emps in sorted(by_month.items()):
            total_gross = sum(e['gross'] for e in emps)
            total_net = sum(e['net'] for e in emps)
            print(f"  {year}-{month:02d}: {len(emps)} employees, Gross=${total_gross:,.2f}, Net=${total_net:,.2f}")
            
            # Show first 3 employees as sample
            print(f"    Sample employees:")
            for emp in emps[:3]:
                print(f"      • {emp['name']}: Gross=${emp['gross']}, Net=${emp['net']}")
    
    return all_employees

if __name__ == '__main__':
    all_employees = main()
