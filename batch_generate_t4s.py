"""
Batch T4 Printing Utility - Employer Format
Generates T4 forms for multiple employees with 2 per page (employer copy)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from desktop_app.t4_official_form_filler import T4OfficialFormFiller
from desktop_app.database import Database


def fetch_all_employees_for_year(db, tax_year):
    """Fetch all employees who had earnings in the given tax year"""
    cur = db.get_cursor()
    cur.execute("""
        SELECT DISTINCT
            e.employee_id,
            e.employee_name,
            COALESCE(e.first_name, '') as first_name,
            COALESCE(e.last_name, '') as last_name,
            e.sin,
            e.address,
            e.city,
            e.province,
            e.postal_code,
            COALESCE(SUM(epm.gross_pay), 0) as total_box14,
            COALESCE(SUM(epm.cpp_employee), 0) as total_box16,
            COALESCE(SUM(epm.ei_employee), 0) as total_box18,
            COALESCE(SUM(epm.federal_tax + epm.provincial_tax), 0) as total_box22,
            COALESCE(SUM(epm.gross_pay), 0) as total_box24,
            COALESCE(SUM(epm.gross_pay), 0) as total_box26,
            COALESCE(SUM(epm.union_dues), 0) as total_box44
        FROM employees e
        INNER JOIN employee_pay_master epm ON e.employee_id = epm.employee_id
        WHERE epm.fiscal_year = %s
        GROUP BY e.employee_id, e.employee_name, e.first_name, e.last_name, e.sin, e.address, e.city, e.province, e.postal_code
        HAVING SUM(epm.gross_pay) > 0
        ORDER BY e.employee_name
    """, (tax_year,))
    
    employees = []
    for row in cur.fetchall():
        employee_data = {
            'employee_id': row[0],
            'full_name': row[1],
            'first_name': row[2],
            'last_name': row[3],
            'sin': row[4],
            'address': row[5],
            'city': row[6],
            'province': row[7] or 'AB',
            'postal_code': row[8],
        }
        
        t4_data = {
            'box14': float(row[9]),
            'box16': float(row[10]),
            'box18': float(row[11]),
            'box22': float(row[12]),
            'box24': float(row[13]),
            'box26': float(row[14]),
            'box44': float(row[15]),
            'box52': 0.0,
        }
        
        employees.append((employee_data, t4_data))
    
    return employees


def generate_batch_t4s_employee_format(tax_year, output_dir='L:/limo/T4_Output'):
    """Generate individual employee-format T4s (2 copies per employee)"""
    from pathlib import Path
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    db = Database()
    db.connect()
    
    try:
        employees = fetch_all_employees_for_year(db, tax_year)
        print(f"Found {len(employees)} employees for tax year {tax_year}")
        
        filler = T4OfficialFormFiller()
        generated = []
        
        for emp_data, t4_data in employees:
            emp_name_safe = emp_data['full_name'].replace(' ', '_').replace('/', '-')
            filename = f"T4_{tax_year}_{emp_name_safe}_EMPLOYEE.pdf"
            file_path = output_path / filename
            
            result = filler.fill_t4_form(emp_data, t4_data, tax_year, str(file_path), 
                                        format_type='employee')
            
            if result:
                generated.append(filename)
                print(f"  Generated: {filename}")
            else:
                print(f"  FAILED: {emp_data['full_name']}")
        
        print(f"\nSUCCESS: Generated {len(generated)} T4 forms")
        print(f"Output directory: {output_path}")
        
        return generated
        
    finally:
        db.close()


def generate_batch_t4s_employer_format(tax_year, output_dir='L:/limo/T4_Output'):
    """Generate employer-format T4s (2 employees per page)"""
    from pathlib import Path
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    db = Database()
    db.connect()
    
    try:
        employees = fetch_all_employees_for_year(db, tax_year)
        print(f"Found {len(employees)} employees for tax year {tax_year}")
        
        filler = T4OfficialFormFiller()
        generated = []
        page_num = 1
        
        # Process in pairs
        for i in range(0, len(employees), 2):
            emp1_data, t4_data1 = employees[i]
            
            # Second employee (if exists)
            if i + 1 < len(employees):
                emp2_data, t4_data2 = employees[i + 1]
            else:
                emp2_data, t4_data2 = None, None
            
            filename = f"T4_{tax_year}_EMPLOYER_Page{page_num:03d}.pdf"
            file_path = output_path / filename
            
            result = filler.fill_t4_employer_format(
                emp1_data, t4_data1,
                emp2_data, t4_data2,
                tax_year, str(file_path)
            )
            
            if result:
                generated.append(filename)
                emp_names = emp1_data['full_name']
                if emp2_data:
                    emp_names += f" + {emp2_data['full_name']}"
                print(f"  Page {page_num}: {emp_names}")
            else:
                print(f"  FAILED: Page {page_num}")
            
            page_num += 1
        
        print(f"\nSUCCESS: Generated {len(generated)} employer T4 pages")
        print(f"Output directory: {output_path}")
        
        return generated
        
    finally:
        db.close()


def main():
    """Command-line interface for batch T4 generation"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate T4 forms in batch')
    parser.add_argument('year', type=int, help='Tax year (e.g., 2025)')
    parser.add_argument('--format', choices=['employee', 'employer'], default='employee',
                       help='employee = 2 copies per employee, employer = 2 employees per page')
    parser.add_argument('--output-dir', default='L:/limo/T4_Output',
                       help='Output directory for T4 PDFs')
    
    args = parser.parse_args()
    
    print(f"Generating T4 forms for tax year {args.year} ({args.format} format)...")
    print()
    
    if args.format == 'employee':
        generate_batch_t4s_employee_format(args.year, args.output_dir)
    else:
        generate_batch_t4s_employer_format(args.year, args.output_dir)


if __name__ == '__main__':
    main()
