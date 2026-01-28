"""
Extract 2012 payroll data from Excel workbooks with complex formatting.

These workbooks have:
- Monthly sheets (Jan.12, Feb.12, etc.)
- Headers in rows 4-5
- Employee data starting around row 5
- Merged cells and inconsistent column positions
"""

import pandas as pd
import os
import sys
from datetime import datetime
from decimal import Decimal

# Excel file paths
WORKBOOKS = [
    r"L:\limo\docs\2012-2013 excel\MASTER COPY 2012 YTD Hourly Payroll Workbook.xls",
    r"L:\limo\docs\2012-2013 excel\MASTER COPY 2012 YTD Hourly Payroll Workbook.xls1.xls",
    r"L:\limo\docs\2012-2013 excel\MASTER COPY 2012 YTD Hourly Payroll Workbook.xls1a.xls"
]

def find_column_by_label(df, row_idx, label):
    """Find column index by searching for label in specific row."""
    try:
        row_data = df.iloc[row_idx]
        for idx, val in enumerate(row_data):
            if isinstance(val, str) and label.lower() in val.lower():
                return idx
    except:
        pass
    return None

def extract_employees_from_sheet(df, sheet_name):
    """Extract employee payroll data from a sheet."""
    employees = []
    
    # Header row is always at row 4 (0-indexed)
    # Employee data starts at row 5
    header_row = 4
    data_start_row = 5
    
    # Fixed column positions based on debug output
    # Row 4: Col 0=Emp.#, Col 1=Name, Col 2=Rate, Col 3=Hours, Col 4=Wages
    #        Col 5=Grat-Tax, Col 6=Grat-Misc, Col 7=Expense Reimburse
    #        Col 8=Total Payable, Col 9=Grat-Paid, Col 10=Expense Reimbursed, Col 11=Advance
    #        Col 12=Total Paid Out, Col 13=Net before deductions
    emp_num_col = 0
    name_col = 1
    rate_col = 2
    hours_col = 3
    wages_col = 4
    grat_taxable_col = 5
    grat_misc_col = 6
    expense_reimburse_col = 7
    total_payable_col = 8
    grat_paid_col = 9
    expense_reimbursed_col = 10
    advance_col = 11
    total_paid_col = 12
    net_before_deductions_col = 13
    
    # Helper to get decimal from row
    def get_decimal(row, col_idx):
        if col_idx >= len(row):
            return Decimal('0')
        val = row.iloc[col_idx]
        if pd.isna(val) or val == '' or str(val).strip().lower() in ['xxx', 'nan', 'x']:
            return Decimal('0')
        try:
            return Decimal(str(val).replace(',', '').replace('$', '').strip())
        except:
            return Decimal('0')
    
    for idx in range(data_start_row, len(df)):
        row = df.iloc[idx]
        
        # Get employee number
        emp_num_val = row.iloc[emp_num_col] if emp_num_col < len(row) else None
        if pd.isna(emp_num_val):
            continue
        
        emp_num = str(emp_num_val).strip()
        
        # Get name
        name_val = row.iloc[name_col] if name_col < len(row) else None
        if pd.isna(name_val):
            continue
        
        name = str(name_val).strip()
        
        # Skip if name is empty or a placeholder
        if not name or name.lower() in ['xxx', 'nan']:
            continue
        
        # Extract financial data
        rate = get_decimal(row, rate_col)
        hours = get_decimal(row, hours_col)
        grat_taxable = get_decimal(row, grat_taxable_col)
        grat_misc = get_decimal(row, grat_misc_col)
        expense_reimburse = get_decimal(row, expense_reimburse_col)
        total_payable = get_decimal(row, total_payable_col)
        grat_paid = get_decimal(row, grat_paid_col)
        expense_reimbursed = get_decimal(row, expense_reimbursed_col)
        advance = get_decimal(row, advance_col)
        total_paid = get_decimal(row, total_paid_col)
        net_before_deductions = get_decimal(row, net_before_deductions_col)
        
        # Skip if all amounts are zero
        if (total_payable == 0 and grat_paid == 0 and expense_reimbursed == 0 and 
            advance == 0 and total_paid == 0 and net_before_deductions == 0):
            continue
        
        employees.append({
            'emp_num': emp_num,
            'name': name,
            'rate': rate,
            'hours': hours,
            'grat_taxable': grat_taxable,
            'grat_misc': grat_misc,
            'expense_reimburse': expense_reimburse,
            'total_payable': total_payable,
            'grat_paid': grat_paid,
            'expense_reimbursed': expense_reimbursed,
            'advance': advance,
            'total_paid': total_paid,
            'net_before_deductions': net_before_deductions,
            'sheet': sheet_name
        })
    
    return employees

def parse_month_year_from_sheet(sheet_name):
    """Parse month and year from sheet name like 'Jan.12' or 'May 2012'."""
    # Remove extra spaces and normalize
    sheet_name = sheet_name.strip()
    
    # Handle formats like "Jan.12", "Feb.12", etc.
    if '.' in sheet_name:
        parts = sheet_name.split('.')
        month_abbr = parts[0].strip()
        year_part = parts[1].strip()
        
        # Convert abbreviation to month number
        month_map = {
            'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
            'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
        }
        month = month_map.get(month_abbr, None)
        
        # Handle 2-digit year
        if len(year_part) == 2:
            year = int('20' + year_part)
        else:
            year = int(year_part)
        
        return month, year
    
    # Handle format like "May 2012"
    if ' ' in sheet_name:
        parts = sheet_name.split()
        month_name = parts[0].strip()
        year = int(parts[1].strip())
        
        month_map = {
            'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
            'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12
        }
        month = month_map.get(month_name, None)
        
        return month, year
    
    return None, None

def main():
    all_payroll = []
    
    for workbook_path in WORKBOOKS:
        if not os.path.exists(workbook_path):
            print(f"[WARN]  Workbook not found: {workbook_path}")
            continue
        
        print(f"\n{'='*80}")
        print(f"Processing: {os.path.basename(workbook_path)}")
        print(f"{'='*80}")
        
        try:
            xls = pd.ExcelFile(workbook_path)
            
            for sheet_name in xls.sheet_names:
                # Skip blank sheets or non-payroll sheets
                if 'blank' in sheet_name.lower() or 'sheet' in sheet_name.lower():
                    continue
                
                # Parse month/year
                month, year = parse_month_year_from_sheet(sheet_name)
                if month is None or year is None:
                    print(f"  [WARN]  Skipping {sheet_name} - can't parse date")
                    continue
                
                # Only process 2012 data
                if year != 2012:
                    continue
                
                print(f"\n  Sheet: {sheet_name} ({year}-{month:02d})")
                
                # Read sheet
                df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
                
                # Extract employees
                employees = extract_employees_from_sheet(df, sheet_name)
                
                if not employees:
                    print(f"    No employee data found")
                    continue
                
                print(f"    Found {len(employees)} employees:")
                for emp in employees:
                    # Add month/year
                    emp['month'] = month
                    emp['year'] = year
                    all_payroll.append(emp)
                    
                    # Print summary
                    print(f"      {emp['emp_num']:>5} {emp['name']:<30} "
                          f"Payable: ${emp['total_payable']:>8.2f}  "
                          f"Paid: ${emp['grat_paid'] + emp['expense_reimbursed']:>8.2f}")
        
        except Exception as e:
            print(f"  [FAIL] Error: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"Total entries extracted: {len(all_payroll)}")
    
    if all_payroll:
        # Group by month
        by_month = {}
        for entry in all_payroll:
            key = f"{entry['year']}-{entry['month']:02d}"
            if key not in by_month:
                by_month[key] = []
            by_month[key].append(entry)
        
        print(f"\nBy month:")
        for month_key in sorted(by_month.keys()):
            entries = by_month[month_key]
            total_payable = sum(e['total_payable'] for e in entries)
            total_paid = sum(e['grat_paid'] + e['expense_reimbursed'] for e in entries)
            print(f"  {month_key}: {len(entries):>2} employees, "
                  f"${total_payable:>10.2f} payable, "
                  f"${total_paid:>10.2f} paid")
        
        # Group by employee
        by_employee = {}
        for entry in all_payroll:
            emp_key = f"{entry['emp_num']} - {entry['name']}"
            if emp_key not in by_employee:
                by_employee[emp_key] = []
            by_employee[emp_key].append(entry)
        
        print(f"\nBy employee:")
        for emp_key in sorted(by_employee.keys()):
            entries = by_employee[emp_key]
            total_payable = sum(e['total_payable'] for e in entries)
            total_paid = sum(e['grat_paid'] + e['expense_reimbursed'] for e in entries)
            print(f"  {emp_key:<40} {len(entries):>2} months, "
                  f"${total_payable:>10.2f} payable, "
                  f"${total_paid:>10.2f} paid")
        
        # Grand totals
        grand_total_payable = sum(e['total_payable'] for e in all_payroll)
        grand_total_paid = sum(e['grat_paid'] + e['expense_reimbursed'] for e in all_payroll)
        print(f"\nGrand totals:")
        print(f"  Total payable: ${grand_total_payable:>12.2f}")
        print(f"  Total paid:    ${grand_total_paid:>12.2f}")
    
    return all_payroll

if __name__ == '__main__':
    payroll_data = main()
