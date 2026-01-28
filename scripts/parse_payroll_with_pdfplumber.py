"""
Parse 2012 Monthly Payroll Summary PDFs using pdfplumber for table extraction.

This handles the structured table format in the payroll summaries.
"""

try:
    import pdfplumber
except ImportError:
    print("Installing pdfplumber...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'pdfplumber'])
    import pdfplumber

from pathlib import Path
from decimal import Decimal
import re

def clean_amount(value):
    """Clean and convert amount string to Decimal."""
    if value is None or value == '' or value == '-':
        return Decimal('0')
    
    # Remove currency symbols, commas, parentheses
    cleaned = str(value).replace('$', '').replace(',', '').replace('(', '-').replace(')', '').strip()
    
    try:
        return Decimal(cleaned)
    except:
        return Decimal('0')

def parse_payroll_summary_table(pdf_path):
    """Parse payroll summary PDF extracting table data."""
    
    filename = Path(pdf_path).name
    
    # Extract month/year from filename
    month_map = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12
    }
    
    month = None
    for month_name, month_num in month_map.items():
        if month_name in filename.lower():
            month = month_num
            break
    
    year_match = re.search(r'20\d{2}', filename)
    year = int(year_match.group()) if year_match else 2012
    
    print(f"\nProcessing: {filename}")
    print(f"  Month: {month}, Year: {year}")
    
    employees = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                print(f"  Page {page_num + 1}:")
                
                # Extract tables
                tables = page.extract_tables()
                
                if not tables:
                    print(f"    No tables found")
                    continue
                
                print(f"    Found {len(tables)} table(s)")
                
                for table_num, table in enumerate(tables):
                    if not table or len(table) < 2:
                        continue
                    
                    print(f"    Table {table_num + 1}: {len(table)} rows x {len(table[0])} columns")
                    
                    # Show first few rows to understand structure
                    print(f"    First row (header): {table[0]}")
                    if len(table) > 1:
                        print(f"    Second row (data): {table[1]}")
                    
                    # Try to identify employee names and extract data
                    # Look for rows with employee names
                    for row in table[1:]:  # Skip header
                        if not row or len(row) < 2:
                            continue
                        
                        # First column usually has employee name
                        name = row[0] if row[0] else ''
                        name = str(name).strip()
                        
                        # Skip empty rows or total rows
                        if not name or 'total' in name.lower() or name == '':
                            continue
                        
                        # Extract financial data from remaining columns
                        # This needs adjustment based on actual column structure
                        employee = {
                            'name': name,
                            'month': month,
                            'year': year,
                            'raw_data': row  # Store raw for inspection
                        }
                        
                        employees.append(employee)
                
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
    
    return employees

def main():
    """Main function."""
    
    pdf_folder = Path(r"L:\limo\pdf")
    
    # Find one August summary to test with
    test_files = list(pdf_folder.glob("August*2012*Payroll*Summary*.pdf"))
    
    if not test_files:
        print("No August 2012 Payroll Summary found")
        return
    
    print("="*80)
    print("2012 PAYROLL SUMMARY PARSER (pdfplumber)")
    print("="*80)
    
    # Test with first file
    test_file = test_files[0]
    print(f"\nTesting with: {test_file.name}\n")
    
    employees = parse_payroll_summary_table(test_file)
    
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    
    if employees:
        print(f"\nExtracted {len(employees)} entries")
        print("\nSample data:")
        for i, emp in enumerate(employees[:5]):
            print(f"\n  Entry {i+1}:")
            print(f"    Name: {emp['name']}")
            print(f"    Month: {emp['month']}")
            print(f"    Raw data: {emp['raw_data']}")
    else:
        print("\nNo employees extracted")
        print("Check the table structure output above to adjust parsing logic")

if __name__ == '__main__':
    main()
