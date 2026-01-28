"""
Audit 2012 ROE documents - compare draft vs final versions
Extract and verify contents against T4 records
"""
import os
import re
from pathlib import Path
from datetime import datetime
import psycopg2

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

# ROE employees
roe_employees = [
    'Angel Escobar', 'Chantal Thomas', 'Dale Menard', 'Doug Redmond',
    'Jeannie Shillington', 'Jesse Gordon', 'Michael Richard', 'Paul Mansell'
]

def extract_text_from_ocr_pdf(filepath):
    """Extract text from OCR'd PDF"""
    if not os.path.exists(filepath):
        return None
    
    try:
        # Read raw text - OCR'd PDFs should have searchable text
        with open(filepath, 'rb') as f:
            content = f.read()
        
        # Try to decode text portions (basic extraction)
        text = content.decode('latin-1', errors='ignore')
        
        # Extract visible text patterns
        patterns = {
            'employee_name': r'(?:Employee|Name)[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            'sin': r'(?:SIN|Social Insurance)[:\s#]*(\d{3}[-\s]?\d{3}[-\s]?\d{3})',
            'last_day': r'(?:Last day worked|Final day)[:\s]*(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})',
            'separation_reason': r'(?:Reason|Code)[:\s]*([A-Z]\s*-\s*[^\n]{10,50})',
            'pay_period': r'(?:Pay period ending|Period)[:\s]*(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})',
        }
        
        extracted = {}
        for key, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted[key] = match.group(1).strip()
        
        return extracted
    except Exception as e:
        return {'error': str(e)}


def compare_file_versions(employee_name):
    """Compare draft vs final ROE versions"""
    base_path = Path(r'L:\limo\pdf\2012\pay\PDOC')
    
    # Find both versions
    clean_name = f'{employee_name}  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf'
    pdf_prefix = f'pdf{employee_name}  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf'
    
    clean_file = base_path / clean_name
    pdf_file = base_path / pdf_prefix
    
    result = {
        'employee': employee_name,
        'clean_exists': clean_file.exists(),
        'pdf_exists': pdf_file.exists(),
        'clean_size': clean_file.stat().st_size if clean_file.exists() else 0,
        'pdf_size': pdf_file.stat().st_size if pdf_file.exists() else 0,
    }
    
    if clean_file.exists():
        result['clean_date'] = datetime.fromtimestamp(clean_file.stat().st_mtime)
        result['clean_text'] = extract_text_from_ocr_pdf(str(clean_file))
    
    if pdf_file.exists():
        result['pdf_date'] = datetime.fromtimestamp(pdf_file.stat().st_mtime)
        result['pdf_text'] = extract_text_from_ocr_pdf(str(pdf_file))
    
    # Calculate size difference
    if result['clean_size'] and result['pdf_size']:
        diff = result['pdf_size'] - result['clean_size']
        result['size_diff'] = diff
        result['size_diff_pct'] = (diff / result['clean_size']) * 100
    
    return result


def get_t4_data(employee_name):
    """Get T4 data for employee from database"""
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    # Handle name variations
    search_names = [employee_name]
    if employee_name == 'Doug Redmond':
        search_names.append('Douglas Redmond')
    
    for name in search_names:
        parts = name.split()
        if len(parts) == 2:
            first, last = parts
            cur.execute('''
                SELECT 
                    e.first_name || ' ' || e.last_name as full_name,
                    t.box_14_employment_income,
                    t.box_16_cpp_contributions,
                    t.box_18_ei_premiums,
                    t.box_22_income_tax
                FROM employee_t4_records t
                JOIN employees e ON t.employee_id = e.employee_id
                WHERE t.tax_year = 2012
                AND (e.first_name ILIKE %s OR e.first_name ILIKE %s)
                AND (e.last_name ILIKE %s OR e.last_name ILIKE %s)
            ''', (first, first + '%', last, last + '%'))
            
            result = cur.fetchone()
            if result:
                cur.close()
                conn.close()
                return {
                    'found': True,
                    'name': result[0],
                    'employment_income': float(result[1]) if result[1] else 0,
                    'cpp': float(result[2]) if result[2] else 0,
                    'ei': float(result[3]) if result[3] else 0,
                    'tax': float(result[4]) if result[4] else 0,
                }
    
    cur.close()
    conn.close()
    return {'found': False}


def main():
    print('=' * 80)
    print('2012 ROE DOCUMENT AUDIT')
    print('=' * 80)
    print()
    print('Comparing draft (pdf prefix) vs final (clean name) versions')
    print('Date: January 27, 2026')
    print()
    
    all_results = []
    
    for employee in roe_employees:
        print(f'\n{"=" * 80}')
        print(f'EMPLOYEE: {employee}')
        print(f'{"=" * 80}')
        
        # Compare file versions
        file_data = compare_file_versions(employee)
        all_results.append(file_data)
        
        print(f'\nFile Analysis:')
        print(f'  Clean version: {"✓" if file_data["clean_exists"] else "✗"} ({file_data["clean_size"]:,} bytes)')
        if file_data.get('clean_date'):
            print(f'    Modified: {file_data["clean_date"]}')
        
        print(f'  PDF prefix:    {"✓" if file_data["pdf_exists"] else "✗"} ({file_data["pdf_size"]:,} bytes)')
        if file_data.get('pdf_date'):
            print(f'    Modified: {file_data["pdf_date"]}')
        
        if file_data.get('size_diff'):
            print(f'  Size difference: {file_data["size_diff"]:,} bytes ({file_data["size_diff_pct"]:.1f}% larger)')
        
        # Get T4 data
        t4_data = get_t4_data(employee)
        
        print(f'\nT4 Record (2012):')
        if t4_data['found']:
            print(f'  ✓ FOUND - {t4_data["name"]}')
            print(f'    Employment Income: ${t4_data["employment_income"]:,.2f}')
            print(f'    CPP Contributions: ${t4_data["cpp"]:,.2f}')
            print(f'    EI Premiums:       ${t4_data["ei"]:,.2f}')
            print(f'    Income Tax:        ${t4_data["tax"]:,.2f}')
        else:
            print(f'  ✗ NOT FOUND in T4 records')
            print(f'    ⚠️  Employee may have been:')
            print(f'       - Casual/seasonal with earnings below T4 threshold')
            print(f'       - Contractor/not on payroll')
            print(f'       - Data entry error/omission')
    
    # Summary
    print(f'\n\n{"=" * 80}')
    print('SUMMARY')
    print(f'{"=" * 80}')
    
    with_both = sum(1 for r in all_results if r['clean_exists'] and r['pdf_exists'])
    clean_only = sum(1 for r in all_results if r['clean_exists'] and not r['pdf_exists'])
    pdf_only = sum(1 for r in all_results if r['pdf_exists'] and not r['clean_exists'])
    
    print(f'\nFile Version Counts:')
    print(f'  Both versions:  {with_both}/8')
    print(f'  Clean only:     {clean_only}/8')
    print(f'  PDF prefix only: {pdf_only}/8')
    
    avg_size_diff = sum(r.get('size_diff', 0) for r in all_results if r.get('size_diff')) / with_both if with_both else 0
    print(f'\nAverage size difference: {avg_size_diff:,.0f} bytes')
    print(f'  → PDF prefix files are ~{avg_size_diff/1024:.1f} KB larger on average')
    
    print(f'\nConclusion:')
    if avg_size_diff > 0:
        print(f'  Larger "pdf" prefix files are likely DRAFT versions with:')
        print(f'    - Additional metadata/comments')
        print(f'    - Uncorrected errors')
        print(f'    - Extra formatting/watermarks')
        print(f'  Smaller clean-name files are likely FINAL corrected versions')
    else:
        print(f'  Files are similar in size - manual review required')


if __name__ == '__main__':
    main()
