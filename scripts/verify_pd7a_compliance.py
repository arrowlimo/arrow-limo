#!/usr/bin/env python3
"""Verify our calculated payroll data matches official PD7A forms filed with CRA.
Extracts data from PD7A PDFs, compares against driver_payroll table, flags discrepancies.
Critical for CRA compliance - any mismatch is a red flag.
"""
import os, sys, psycopg2, glob
from PyPDF2 import PdfReader
import re

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REDACTED***')
    )

def table_has_column(cur, table, column):
    cur.execute("SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s", (table, column))
    return cur.fetchone() is not None

def extract_pd7a_year_totals(pdf_path):
    """Extract year-end totals from PD7A PDF"""
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        
        # Look for year
        year_match = re.search(r'20(1[2-9]|2[0-5])', os.path.basename(pdf_path))
        year = int(year_match.group(0)) if year_match else None
        
        # Extract key amounts (various formats in PD7A forms)
        # Total remuneration paid (Box 14 equivalent)
        gross_patterns = [
            r'Total remuneration paid.*?[\$]?\s*([0-9,]+\.[0-9]{2})',
            r'Gross payroll.*?[\$]?\s*([0-9,]+\.[0-9]{2})',
            r'Employment income.*?[\$]?\s*([0-9,]+\.[0-9]{2})'
        ]
        
        # CPP employee deductions
        cpp_patterns = [
            r'CPP.*?employee.*?[\$]?\s*([0-9,]+\.[0-9]{2})',
            r'Pensionable earnings.*?deductions.*?[\$]?\s*([0-9,]+\.[0-9]{2})'
        ]
        
        # EI employee deductions
        ei_patterns = [
            r'EI.*?employee.*?[\$]?\s*([0-9,]+\.[0-9]{2})',
            r'Insurable earnings.*?deductions.*?[\$]?\s*([0-9,]+\.[0-9]{2})'
        ]
        
        # Income tax deducted
        tax_patterns = [
            r'Income tax deducted.*?[\$]?\s*([0-9,]+\.[0-9]{2})',
            r'Federal tax.*?[\$]?\s*([0-9,]+\.[0-9]{2})',
            r'Tax withheld.*?[\$]?\s*([0-9,]+\.[0-9]{2})'
        ]
        
        def extract_amount(patterns):
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return float(match.group(1).replace(',',''))
            return None
        
        return {
            'year': year,
            'source_file': os.path.basename(pdf_path),
            'gross_payroll': extract_amount(gross_patterns),
            'cpp_employee': extract_amount(cpp_patterns),
            'ei_employee': extract_amount(ei_patterns),
            'income_tax': extract_amount(tax_patterns)
        }
    except Exception as e:
        print(f"Error parsing {pdf_path}: {e}")
        return None

def get_our_calculated_totals(cur, year):
    """Get our calculated totals from driver_payroll table"""
    has_pay_date = table_has_column(cur, 'driver_payroll', 'pay_date')
    date_col = 'pay_date' if has_pay_date else 'imported_at'
    
    base = f"""
    SELECT 
        ROUND(COALESCE(SUM(gross_pay),0)::numeric,2) as gross,
        ROUND(COALESCE(SUM(cpp),0)::numeric,2) as cpp,
        ROUND(COALESCE(SUM(ei),0)::numeric,2) as ei,
        ROUND(COALESCE(SUM(tax),0)::numeric,2) as tax
    FROM driver_payroll 
    WHERE {date_col} >= %s AND {date_col} < %s
    """
    
    if table_has_column(cur, 'driver_payroll', 'payroll_class'):
        base += " AND (payroll_class <> 'ADJUSTMENT' OR payroll_class IS NULL)"
    
    start = f"{year}-01-01"
    end = f"{year+1}-01-01"
    cur.execute(base, (start, end))
    row = cur.fetchone()
    
    return {
        'year': year,
        'gross_payroll': float(row[0]) if row[0] else 0,
        'cpp_employee': float(row[1]) if row[1] else 0,
        'ei_employee': float(row[2]) if row[2] else 0,
        'income_tax': float(row[3]) if row[3] else 0
    }

def compare_and_flag(pd7a_data, our_data, tolerance=10.00):
    """Compare PD7A vs our calculations, flag discrepancies"""
    issues = []
    
    if not pd7a_data or not our_data:
        return ['MISSING_DATA']
    
    fields = ['gross_payroll', 'cpp_employee', 'ei_employee', 'income_tax']
    
    for field in fields:
        pd7a_val = pd7a_data.get(field)
        our_val = our_data.get(field)
        
        if pd7a_val is None or our_val is None:
            issues.append(f"{field.upper()}_MISSING_IN_SOURCE")
            continue
        
        diff = abs(pd7a_val - our_val)
        pct = (diff / pd7a_val * 100) if pd7a_val > 0 else 0
        
        if diff > tolerance:
            issues.append(f"{field.upper()}_MISMATCH: PD7A=${pd7a_val:,.2f} vs Ours=${our_val:,.2f} (diff=${diff:,.2f}, {pct:.1f}%)")
    
    return issues if issues else ['OK']

def main():
    # Find all PD7A PDFs for 2012-2015
    pd7a_paths = glob.glob(r"L:\limo\quickbooks\**\*PD7A*.pdf", recursive=True)
    pd7a_paths.extend(glob.glob(r"L:\limo\pdf\**\*PD7A*.pdf", recursive=True))
    
    # Filter for years 2012-2015
    year_files = {}
    for path in pd7a_paths:
        basename = os.path.basename(path)
        # Skip monthly reports, look for year-end summaries
        if 'Year End' in basename or 'TOTAL' in basename:
            year_match = re.search(r'20(1[2-5])', basename)
            if year_match:
                year = int(year_match.group(0))
                if year not in year_files:
                    year_files[year] = path
    
    conn = get_conn()
    cur = conn.cursor()
    
    print("=" * 80)
    print("CRA PD7A COMPLIANCE VERIFICATION (2012-2015)")
    print("=" * 80)
    print()
    
    all_ok = True
    
    for year in sorted([2012, 2013, 2014, 2015]):
        print(f"\n{'='*80}")
        print(f"YEAR {year}")
        print(f"{'='*80}")
        
        pd7a_path = year_files.get(year)
        
        if pd7a_path:
            print(f"Official PD7A: {os.path.basename(pd7a_path)}")
            pd7a_data = extract_pd7a_year_totals(pd7a_path)
        else:
            print(f"[WARN]  NO OFFICIAL PD7A FOUND FOR {year}")
            pd7a_data = None
        
        our_data = get_our_calculated_totals(cur, year)
        
        print(f"\nComparison:")
        print(f"{'Component':<25} {'Official PD7A':<20} {'Our Calculation':<20} {'Difference':<15}")
        print(f"{'-'*80}")
        
        if pd7a_data:
            for field in ['gross_payroll', 'cpp_employee', 'ei_employee', 'income_tax']:
                pd7a_val = pd7a_data.get(field, 0) or 0
                our_val = our_data.get(field, 0) or 0
                diff = our_val - pd7a_val
                
                status = "✓" if abs(diff) <= 10 else "[FAIL]"
                print(f"{field:<25} ${pd7a_val:>15,.2f}   ${our_val:>15,.2f}   {status} ${diff:>10,.2f}")
        else:
            for field in ['gross_payroll', 'cpp_employee', 'ei_employee', 'income_tax']:
                our_val = our_data.get(field, 0) or 0
                print(f"{field:<25} {'N/A':<20} ${our_val:>15,.2f}   {'[WARN] UNVERIFIED'}")
        
        issues = compare_and_flag(pd7a_data, our_data)
        
        if issues != ['OK']:
            all_ok = False
            print(f"\n🚨 ISSUES FOUND:")
            for issue in issues:
                print(f"   - {issue}")
        else:
            print(f"\n[OK] All amounts match within tolerance")
    
    cur.close()
    conn.close()
    
    print(f"\n{'='*80}")
    if all_ok:
        print("[OK] VERIFICATION PASSED: Our data matches official PD7A forms")
    else:
        print("[FAIL] VERIFICATION FAILED: Discrepancies found - MUST INVESTIGATE")
    print(f"{'='*80}\n")
    
    return 0 if all_ok else 1

if __name__ == '__main__':
    sys.exit(main())
