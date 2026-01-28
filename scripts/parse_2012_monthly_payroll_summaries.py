"""
Parse 2012 Monthly Payroll Summary PDFs

Extracts employee-level payroll data from the structured monthly summary PDFs
(August, September, October, November 2012).

Based on the August 2012 format shown:
- Employee rows with Hours, Wages, Gratuities, Expenses
- Tax withholdings (CPP, EI, Federal/Provincial Tax)
- Net pay calculations
"""

import PyPDF2
import re
from decimal import Decimal
from pathlib import Path
import sys

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file."""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ''
            for page in reader.pages:
                text += page.extract_text()
            return text
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
        return None

def parse_august_2012_format(text, month, year):
    """
    Parse August 2012 Payroll Summary format.
    
    Expected structure:
    Employee name followed by financial columns:
    - Hours (Salary/Wages columns)
    - Gratuities (Taxable, Credit Card, Expense Reimbursement)
    - Total Gross Pay
    - Taxes Withheld (Federal, CPP, EI)
    - Net Pay
    """
    
    employees = []
    
    # Employee name patterns (from August 2012 PDF)
    employee_names = [
        'Angel Escobar', 'Chantal Thomas', 'Dale Menard', 'Doug Redmond',
        'Dustan Townsend', 'Jeannie Gordon', 'Jesse Gordon', 'Michael Richard',
        'Paul D Richard', 'Paul Mansell', 'Zak Keller',
        # Additional common names
        'Kevin', 'Mark', 'Carla', 'Erik', 'Barney', 'Andrew', 'Flinn'
    ]
    
    lines = text.split('\n')
    
    # Find the data rows
    in_employee_section = False
    current_employee = None
    
    for i, line in enumerate(lines):
        # Check if line contains an employee name
        for name in employee_names:
            if name in line:
                current_employee = name
                in_employee_section = True
                
                # Try to extract numbers from this line and surrounding lines
                # Look for pattern: name followed by numbers
                
                # Combine this line with next few lines for number extraction
                data_block = ' '.join(lines[i:min(i+3, len(lines))])
                
                # Extract all decimal numbers from the data block
                numbers = re.findall(r'\d+\.\d+|\d+', data_block)
                
                if len(numbers) >= 5:  # Need at least hours, wages, grat, expense, gross
                    try:
                        # Parse based on expected column order
                        # This is a simplified extraction - actual parsing needs adjustment
                        # based on exact PDF layout
                        
                        employee = {
                            'name': name,
                            'month': month,
                            'year': year,
                            'hours': Decimal(numbers[0]) if len(numbers) > 0 else Decimal('0'),
                            'wages': Decimal(numbers[1]) if len(numbers) > 1 else Decimal('0'),
                            'gratuities': Decimal(numbers[2]) if len(numbers) > 2 else Decimal('0'),
                            'expenses': Decimal(numbers[3]) if len(numbers) > 3 else Decimal('0'),
                            'gross_pay': Decimal(numbers[4]) if len(numbers) > 4 else Decimal('0'),
                            'cpp': Decimal('0'),
                            'ei': Decimal('0'),
                            'tax': Decimal('0'),
                            'net_pay': Decimal('0')
                        }
                        
                        # Try to find tax withholdings (usually later in the line)
                        if len(numbers) > 7:
                            employee['cpp'] = Decimal(numbers[5]) if len(numbers) > 5 else Decimal('0')
                            employee['ei'] = Decimal(numbers[6]) if len(numbers) > 6 else Decimal('0')
                            employee['tax'] = Decimal(numbers[7]) if len(numbers) > 7 else Decimal('0')
                        
                        if len(numbers) > 8:
                            employee['net_pay'] = Decimal(numbers[8])
                        
                        employees.append(employee)
                        
                    except (ValueError, IndexError) as e:
                        print(f"Warning: Could not parse numbers for {name}: {e}")
                
                break
    
    return employees

def parse_monthly_summary(pdf_path):
    """Parse a monthly payroll summary PDF."""
    
    # Extract month and year from filename
    filename = Path(pdf_path).name
    
    month_map = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12
    }
    
    month = None
    year = None
    
    for month_name, month_num in month_map.items():
        if month_name in filename.lower():
            month = month_num
            break
    
    year_match = re.search(r'20\d{2}', filename)
    if year_match:
        year = int(year_match.group())
    
    if not month or not year:
        print(f"Could not determine month/year from filename: {filename}")
        return []
    
    print(f"\nProcessing: {filename}")
    print(f"  Month: {month}, Year: {year}")
    
    # Extract text
    text = extract_text_from_pdf(pdf_path)
    if not text:
        return []
    
    # Parse based on format
    employees = parse_august_2012_format(text, month, year)
    
    return employees

def main():
    """Main function to parse all available monthly summaries."""
    
    # PDF locations
    pdf_folder = Path(r"L:\limo\pdf")
    docs_folder = Path(r"L:\limo\docs")
    
    # Find monthly summary PDFs
    summary_files = []
    
    for folder in [pdf_folder, docs_folder]:
        for pattern in ['*August*2012*Payroll*Summary*.pdf',
                       '*September*2012*Payroll*Summary*.pdf',
                       '*October*2012*Payroll*Summary*.pdf',
                       '*November*2012*Payroll*Summary*.pdf']:
            for file in folder.glob(pattern):
                if file not in summary_files:
                    summary_files.append(file)
    
    print("="*80)
    print("2012 MONTHLY PAYROLL SUMMARY PARSER")
    print("="*80)
    
    print(f"\nFound {len(summary_files)} monthly summary files:")
    for f in summary_files:
        print(f"  • {f.name}")
    
    all_employees = []
    
    for pdf_file in summary_files:
        employees = parse_monthly_summary(pdf_file)
        
        if employees:
            print(f"  [OK] Extracted {len(employees)} employees")
            all_employees.extend(employees)
        else:
            print(f"  [WARN]  No data extracted - may need manual parsing")
    
    # Summary
    print("\n" + "="*80)
    print("EXTRACTION SUMMARY")
    print("="*80)
    
    if all_employees:
        print(f"\nTotal employees extracted: {len(all_employees)}")
        
        # Group by month
        by_month = {}
        for emp in all_employees:
            key = f"{emp['year']}-{emp['month']:02d}"
            if key not in by_month:
                by_month[key] = []
            by_month[key].append(emp)
        
        print("\nBy month:")
        for month_key in sorted(by_month.keys()):
            emps = by_month[month_key]
            total_gross = sum(e['gross_pay'] for e in emps)
            print(f"  {month_key}: {len(emps)} employees, ${total_gross:,.2f} gross")
        
        # Show sample data
        print("\nSample employee data:")
        for emp in all_employees[:3]:
            print(f"  {emp['name']:20} {emp['year']}-{emp['month']:02d}  "
                  f"Gross: ${emp['gross_pay']:>10.2f}  "
                  f"Net: ${emp['net_pay']:>10.2f}")
    else:
        print("\n[WARN]  No data extracted from PDFs")
        print("\nThis likely means:")
        print("  1. PDF format is complex and needs custom parsing")
        print("  2. Text extraction is incomplete")
        print("  3. Numbers are in table format requiring different approach")
        print("\nRecommendation:")
        print("  • Use tabula-py or pdfplumber for table extraction")
        print("  • Or manually transcribe the August summary to verify format")
        print("  • Then build targeted parser based on actual layout")
    
    return all_employees

if __name__ == '__main__':
    employees = main()
