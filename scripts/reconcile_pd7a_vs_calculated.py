#!/usr/bin/env python3
"""Query staging_pd7a_year_end_summary and compare against driver_payroll calculations.
Generate reconciliation report showing discrepancies that need investigation.
"""
import os, psycopg2

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REMOVED***')
    )

def table_has_column(cur, table, column):
    cur.execute("SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s", (table, column))
    return cur.fetchone() is not None

def get_pd7a_data(cur, year):
    cur.execute("""
        SELECT year, gross_payroll, num_employees_paid, total_remittance,
               cpp_employee, ei_employee, tax_deductions, source_file
        FROM staging_pd7a_year_end_summary
        WHERE year = %s
    """, (year,))
    row = cur.fetchone()
    if not row:
        return None
    return {
        'year': row[0],
        'gross_payroll': float(row[1]) if row[1] else 0,
        'employees_paid': int(row[2]) if row[2] else 0,
        'total_remittance': float(row[3]) if row[3] else 0,
        'cpp_employee': float(row[4]) if row[4] else 0,
        'ei_employee': float(row[5]) if row[5] else 0,
        'income_tax': float(row[6]) if row[6] else 0,
        'source_file': row[7]
    }

def get_our_calculated(cur, year):
    has_pay_date = table_has_column(cur, 'driver_payroll', 'pay_date')
    date_col = 'pay_date' if has_pay_date else 'imported_at'
    
    base = f"""
    SELECT 
        COUNT(DISTINCT driver_id) as employee_count,
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
        'employee_count': int(row[0]) if row[0] else 0,
        'gross_payroll': float(row[1]) if row[1] else 0,
        'cpp_employee': float(row[2]) if row[2] else 0,
        'ei_employee': float(row[3]) if row[3] else 0,
        'income_tax': float(row[4]) if row[4] else 0
    }

def main():
    conn = get_conn()
    cur = conn.cursor()
    
    print("\n" + "="*90)
    print("PD7A RECONCILIATION REPORT - Official vs Calculated")
    print("="*90 + "\n")
    
    for year in [2012, 2013, 2014, 2015]:
        pd7a = get_pd7a_data(cur, year)
        calc = get_our_calculated(cur, year)
        
        print(f"\n{'='*90}")
        print(f"YEAR {year}")
        if pd7a:
            print(f"Source: {pd7a['source_file']}")
        else:
            print("[WARN]  NO OFFICIAL PD7A DATA IN STAGING TABLE")
        print(f"{'='*90}")
        
        if not pd7a:
            print(f"\n  Our Calculated Gross Payroll: ${calc['gross_payroll']:>15,.2f}")
            print(f"  [WARN]  CANNOT VERIFY - No official PD7A data")
            continue
        
        # Compare gross payroll
        gross_diff = calc['gross_payroll'] - pd7a['gross_payroll']
        gross_pct = (abs(gross_diff) / pd7a['gross_payroll'] * 100) if pd7a['gross_payroll'] > 0 else 0
        
        print(f"\n  GROSS PAYROLL:")
        print(f"    Official PD7A:      ${pd7a['gross_payroll']:>15,.2f}")
        print(f"    Our Calculation:    ${calc['gross_payroll']:>15,.2f}")
        print(f"    Difference:         ${gross_diff:>15,.2f}  ({gross_pct:>5.1f}%)")
        
        if abs(gross_diff) > 100:
            print(f"    [FAIL] SIGNIFICANT DISCREPANCY - REQUIRES INVESTIGATION")
        elif abs(gross_diff) > 10:
            print(f"    [WARN]  Minor discrepancy - verify rounding")
        else:
            print(f"    [OK] Match within tolerance")
        
        # Compare CPP
        if pd7a['cpp_employee'] > 0:
            cpp_diff = calc['cpp_employee'] - pd7a['cpp_employee']
            print(f"\n  CPP EMPLOYEE:")
            print(f"    Official PD7A:      ${pd7a['cpp_employee']:>15,.2f}")
            print(f"    Our Calculation:    ${calc['cpp_employee']:>15,.2f}")
            print(f"    Difference:         ${cpp_diff:>15,.2f}")
            if abs(cpp_diff) > 10:
                print(f"    [FAIL] MISMATCH")
        
        # Compare EI
        if pd7a['ei_employee'] > 0:
            ei_diff = calc['ei_employee'] - pd7a['ei_employee']
            print(f"\n  EI EMPLOYEE:")
            print(f"    Official PD7A:      ${pd7a['ei_employee']:>15,.2f}")
            print(f"    Our Calculation:    ${calc['ei_employee']:>15,.2f}")
            print(f"    Difference:         ${ei_diff:>15,.2f}")
            if abs(ei_diff) > 10:
                print(f"    [FAIL] MISMATCH")
        
        # Compare Tax
        if pd7a['income_tax'] > 0:
            tax_diff = calc['income_tax'] - pd7a['income_tax']
            print(f"\n  INCOME TAX:")
            print(f"    Official PD7A:      ${pd7a['income_tax']:>15,.2f}")
            print(f"    Our Calculation:    ${calc['income_tax']:>15,.2f}")
            print(f"    Difference:         ${tax_diff:>15,.2f}")
            if abs(tax_diff) > 10:
                print(f"    [FAIL] MISMATCH")
        
        # Employee count
        if pd7a['employees_paid'] > 0:
            print(f"\n  EMPLOYEES:")
            print(f"    Official PD7A:      {pd7a['employees_paid']:>15}")
            print(f"    Our Calculation:    {calc['employee_count']:>15}")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*90)
    print("CRITICAL: Any significant discrepancy must be resolved before filing.")
    print("Potential causes: Missing payroll entries, adjustment misclassification,")
    print("date range issues, or data corruption.")
    print("="*90 + "\n")

if __name__ == '__main__':
    main()
