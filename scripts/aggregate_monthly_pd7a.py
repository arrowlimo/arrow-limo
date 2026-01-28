#!/usr/bin/env python3
"""Aggregate monthly PD7A reports to get year-end totals for comparison."""
import os, psycopg2

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REMOVED***')
    )

def aggregate_pd7a_by_year(cur):
    """Aggregate monthly PD7A data by year"""
    query = """
    SELECT 
        year,
        COUNT(*) as report_count,
        STRING_AGG(DISTINCT source_file, ', ' ORDER BY source_file) as source_files,
        SUM(gross_payroll) as total_gross,
        SUM(cpp_employee) as total_cpp,
        SUM(ei_employee) as total_ei,
        SUM(tax_deductions) as total_tax,
        SUM(total_remittance) as total_remittance,
        MAX(num_employees_paid) as max_employees
    FROM staging_pd7a_year_end_summary
    GROUP BY year
    ORDER BY year
    """
    
    cur.execute(query)
    results = []
    for row in cur.fetchall():
        results.append({
            'year': int(row[0]),
            'report_count': int(row[1]),
            'source_files': row[2],
            'total_gross': float(row[3] or 0),
            'total_cpp': float(row[4] or 0),
            'total_ei': float(row[5] or 0),
            'total_tax': float(row[6] or 0),
            'total_remittance': float(row[7] or 0),
            'max_employees': int(row[8] or 0)
        })
    
    return results

def get_calculated_totals(cur, year):
    """Get calculated totals from driver_payroll"""
    from reconcile_pd7a_vs_calculated import table_has_column
    
    has_pay_date = table_has_column(cur, 'driver_payroll', 'pay_date')
    date_col = 'pay_date' if has_pay_date else 'imported_at'
    
    query = f"""
    SELECT 
        COUNT(*) as entry_count,
        COUNT(DISTINCT driver_id) as num_drivers,
        ROUND(SUM(COALESCE(gross_pay, 0))::numeric, 2) as total_gross,
        ROUND(SUM(COALESCE(cpp, 0))::numeric, 2) as total_cpp,
        ROUND(SUM(COALESCE(ei, 0))::numeric, 2) as total_ei,
        ROUND(SUM(COALESCE(tax, 0))::numeric, 2) as total_tax
    FROM driver_payroll
    WHERE {date_col} >= %s AND {date_col} < %s
    """
    
    if table_has_column(cur, 'driver_payroll', 'payroll_class'):
        query += " AND (payroll_class <> 'ADJUSTMENT' OR payroll_class IS NULL)"
    
    start = f"{year}-01-01"
    end = f"{year+1}-01-01"
    cur.execute(query, (start, end))
    row = cur.fetchone()
    
    return {
        'entry_count': int(row[0]),
        'num_drivers': int(row[1]),
        'total_gross': float(row[2] or 0),
        'total_cpp': float(row[3] or 0),
        'total_ei': float(row[4] or 0),
        'total_tax': float(row[5] or 0)
    }

def main():
    conn = get_conn()
    cur = conn.cursor()
    
    print(f"\n{'='*100}")
    print(f"PD7A MONTHLY AGGREGATION - Official Totals vs Calculated")
    print(f"{'='*100}\n")
    
    aggregates = aggregate_pd7a_by_year(cur)
    
    for agg in aggregates:
        year = agg['year']
        
        print(f"\n{'='*100}")
        print(f"YEAR {year}")
        print(f"{'='*100}")
        print(f"PD7A Reports Found: {agg['report_count']}")
        
        if agg['report_count'] == 1:
            print(f"[WARN]  Only 1 report - likely a single month, not full year")
        
        print(f"\nSource Files:")
        for source in agg['source_files'].split(', '):
            print(f"  - {source}")
        
        # Get calculated totals
        calc = get_calculated_totals(cur, year)
        
        print(f"\n{'Metric':<25} {'Official PD7A':>20} {'Our Calculation':>20} {'Difference':>20}")
        print(f"{'-'*100}")
        
        # Gross Payroll
        gross_diff = calc['total_gross'] - agg['total_gross']
        gross_pct = (gross_diff / agg['total_gross'] * 100) if agg['total_gross'] > 0 else 0
        gross_status = "✓" if abs(gross_pct) < 5 else "[FAIL]"
        print(f"{'Gross Payroll':<25} ${agg['total_gross']:>19,.2f} ${calc['total_gross']:>19,.2f} ${gross_diff:>14,.2f} ({gross_pct:>5.1f}%) {gross_status}")
        
        # CPP
        cpp_diff = calc['total_cpp'] - agg['total_cpp']
        cpp_status = "✓" if abs(cpp_diff) < agg['total_cpp'] * 0.1 else "[FAIL]"
        print(f"{'CPP Employee':<25} ${agg['total_cpp']:>19,.2f} ${calc['total_cpp']:>19,.2f} ${cpp_diff:>19,.2f} {cpp_status}")
        
        # EI
        ei_diff = calc['total_ei'] - agg['total_ei']
        ei_status = "✓" if abs(ei_diff) < agg['total_ei'] * 0.1 else "[FAIL]"
        print(f"{'EI Employee':<25} ${agg['total_ei']:>19,.2f} ${calc['total_ei']:>19,.2f} ${ei_diff:>19,.2f} {ei_status}")
        
        # Tax
        tax_diff = calc['total_tax'] - agg['total_tax']
        tax_status = "✓" if abs(tax_diff) < agg['total_tax'] * 0.1 else "[FAIL]"
        print(f"{'Income Tax':<25} ${agg['total_tax']:>19,.2f} ${calc['total_tax']:>19,.2f} ${tax_diff:>19,.2f} {tax_status}")
        
        # Employees
        emp_diff = calc['num_drivers'] - agg['max_employees']
        print(f"{'Employees':<25} {agg['max_employees']:>20} {calc['num_drivers']:>20} {emp_diff:>20}")
        
        # Summary
        if agg['report_count'] == 1:
            print(f"\n[WARN]  Single report only - cannot validate full year totals")
        elif abs(gross_pct) < 5:
            print(f"\n✓ GROSS PAYROLL RECONCILED within 5%")
            if abs(cpp_diff) > agg['total_cpp'] * 0.1 or abs(ei_diff) > agg['total_ei'] * 0.1 or abs(tax_diff) > agg['total_tax'] * 0.1:
                print(f"[WARN]  Deductions show discrepancies - investigate missing payroll entries")
        else:
            print(f"\n[FAIL] SIGNIFICANT DISCREPANCY - {abs(gross_pct):.1f}%")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
