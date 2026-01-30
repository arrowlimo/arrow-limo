import os
import re
import pdfplumber
import psycopg2
from datetime import datetime

PG_DB = os.getenv('PGDATABASE', 'almsdata')
PG_USER = os.getenv('PGUSER', 'postgres')
PG_HOST = os.getenv('PGHOST', 'localhost')
PG_PORT = os.getenv('PGPORT', '5432')
PG_PASSWORD = os.getenv('PGPASSWORD', '***REDACTED***')

def connect_db():
    return psycopg2.connect(
        dbname=PG_DB, user=PG_USER, host=PG_HOST, port=PG_PORT, password=PG_PASSWORD
    )

def parse_pd7a_monthly(pdf_path, filename):
    """Extract monthly PD7A data and infer year/month from filename"""
    data = {
        'year': None,
        'month': None,
        'period_start': None,
        'period_end': None,
        'gross_payroll': None,
        'num_employees_paid': None,
        'tax_deductions': None,
        'cpp_employee': None,
        'cpp_company': None,
        'total_cpp': None,
        'ei_employee': None,
        'ei_company': None,
        'total_ei': None,
        'total_remittance': None
    }
    
    try:
        # Extract year and month from filename (e.g., "Mar.2014 PD7A.pdf" or "2Mar.2014 PD7A.pdf")
        year_match = re.search(r'(\d{4})', filename)
        if year_match:
            data['year'] = int(year_match.group(1))
        
        month_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', filename, re.IGNORECASE)
        if month_match:
            month_name = month_match.group(1).capitalize()
            month_num = datetime.strptime(month_name, '%b').month
            data['month'] = month_num
            
            if data['year']:
                # Calculate period start and end
                from calendar import monthrange
                _, last_day = monthrange(data['year'], month_num)
                data['period_start'] = f"{data['year']}-{month_num:02d}-01"
                data['period_end'] = f"{data['year']}-{month_num:02d}-{last_day:02d}"
        
        with pdfplumber.open(pdf_path) as pdf:
            text = pdf.pages[0].extract_text()
            if not text:
                return None
            
            # Extract gross payroll
            gross_match = re.search(r'Gross payroll for period\s+([\d,]+\.\d{2})', text)
            if gross_match:
                data['gross_payroll'] = float(gross_match.group(1).replace(',', ''))
            
            # Extract number of employees
            emp_match = re.search(r'No\. of employees paid.*?\s+(\d+)', text)
            if emp_match:
                data['num_employees_paid'] = int(emp_match.group(1))
            
            # Extract tax deductions
            tax_match = re.search(r'Tax deductions\s+([\d,]+\.\d{2})', text)
            if tax_match:
                data['tax_deductions'] = float(tax_match.group(1).replace(',', ''))
            
            # Extract CPP
            cpp_emp_match = re.search(r'CPP - Employee\s+([\d,]+\.\d{2})', text)
            if cpp_emp_match:
                data['cpp_employee'] = float(cpp_emp_match.group(1).replace(',', ''))
            
            cpp_co_match = re.search(r'CPP - Company\s+([\d,]+\.\d{2})', text)
            if cpp_co_match:
                data['cpp_company'] = float(cpp_co_match.group(1).replace(',', ''))
            
            total_cpp_match = re.search(r'Total CPP contributions\s+([\d,]+\.\d{2})', text)
            if total_cpp_match:
                data['total_cpp'] = float(total_cpp_match.group(1).replace(',', ''))
            
            # Extract EI
            ei_emp_match = re.search(r'EI - Employee\s+([\d,]+\.\d{2})', text)
            if ei_emp_match:
                data['ei_employee'] = float(ei_emp_match.group(1).replace(',', ''))
            
            ei_co_match = re.search(r'EI - Company\s+([\d,]+\.\d{2})', text)
            if ei_co_match:
                data['ei_company'] = float(ei_co_match.group(1).replace(',', ''))
            
            total_ei_match = re.search(r'Total EI premiums\s+([\d,]+\.\d{2})', text)
            if total_ei_match:
                data['total_ei'] = float(total_ei_match.group(1).replace(',', ''))
            
            # Extract total remittance (last occurrence)
            remit_matches = re.findall(r'Remittance for period\s+([\d,]+\.\d{2})', text)
            if remit_matches:
                data['total_remittance'] = float(remit_matches[-1].replace(',', ''))
            
            if data['year'] and data['month']:
                print(f"Parsed PD7A for {data['year']}-{data['month']:02d}:")
                print(f"  Gross payroll: ${data['gross_payroll']:,.2f}")
                print(f"  Employees paid: {data['num_employees_paid']}")
                print(f"  Total remittance: ${data['total_remittance']:,.2f}")
            
            return data if data['year'] else None
    
    except Exception as e:
        print(f"Error parsing {pdf_path}: {e}")
        import traceback
        traceback.print_exc()
        return None

def insert_pd7a_monthly(data, source_file):
    """Insert monthly PD7A summary"""
    if not data or not data['year']:
        return
    
    conn = connect_db()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO staging_pd7a_year_end_summary 
        (year, period_start, period_end, gross_payroll, num_employees_paid, 
         tax_deductions, cpp_employee, cpp_company, total_cpp, 
         ei_employee, ei_company, total_ei, total_remittance, source_file)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        data['year'],
        data['period_start'],
        data['period_end'],
        data['gross_payroll'],
        data['num_employees_paid'],
        data['tax_deductions'],
        data['cpp_employee'],
        data['cpp_company'],
        data['total_cpp'],
        data['ei_employee'],
        data['ei_company'],
        data['total_ei'],
        data['total_remittance'],
        source_file
    ))
    
    conn.commit()
    cur.close()
    conn.close()

def main():
    import glob
    pd7a_files = glob.glob(r"L:\limo\quickbooks\**\*PD7A*.pdf", recursive=True)
    
    count = 0
    for pdf_path in pd7a_files:
        if os.path.exists(pdf_path):
            filename = os.path.basename(pdf_path)
            data = parse_pd7a_monthly(pdf_path, filename)
            if data:
                insert_pd7a_monthly(data, pdf_path)
                count += 1
                
                # Mark as excluded
                conn = connect_db()
                cur = conn.cursor()
                cur.execute("""
                    UPDATE staging_driver_pay_files
                    SET status = 'excluded', 
                        error_message = 'Reference data: PD7A payroll summary - extracted to staging_pd7a_year_end_summary'
                    WHERE file_path = %s
                """, (pdf_path,))
                conn.commit()
                cur.close()
                conn.close()
    
    print(f"\nProcessed {count} PD7A files")
    
    # Summary by year
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT year, COUNT(*), SUM(gross_payroll)
        FROM staging_pd7a_year_end_summary
        GROUP BY year
        ORDER BY year
    """)
    print("\n" + "="*80)
    print("PD7A SUMMARY BY YEAR")
    print("="*80)
    for year, count, total in cur.fetchall():
        print(f"{year}: {count:2d} periods, Total gross payroll: ${total:,.2f}")
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
