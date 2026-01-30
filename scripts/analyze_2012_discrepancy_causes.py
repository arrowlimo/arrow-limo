"""
Analyze 2012 payroll discrepancies to identify missing data components
that prevent database totals from matching T4 box values.
"""
import psycopg2
import csv
from decimal import Decimal

def load_cra_t4_data():
    """Load CRA T4 data from CSV"""
    cra_data = {}
    with open(r'l:\limo\data\2012_cra_t4_complete_extraction.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name_key = f"{row['last_name']}, {row['first_name']}".upper()
            cra_data[name_key] = {
                'box_14': Decimal(row['box_14']) if row['box_14'] else Decimal('0'),
                'box_16': Decimal(row['box_16']) if row['box_16'] else Decimal('0'),
                'box_18': Decimal(row['box_18']) if row['box_18'] else Decimal('0'),
                'box_22': Decimal(row['box_22']) if row['box_22'] else Decimal('0'),
                'box_24': Decimal(row['box_24']) if row['box_24'] else Decimal('0'),
                'box_26': Decimal(row['box_26']) if row['box_26'] else Decimal('0'),
            }
    return cra_data

def main():
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    cur = conn.cursor()
    
    # Load CRA data
    cra_data = load_cra_t4_data()
    
    print("=" * 80)
    print("2012 PAYROLL DISCREPANCY ANALYSIS")
    print("=" * 80)
    
    # Analyze each employee's payroll components
    cur.execute("""
        SELECT 
            e.employee_id,
            e.full_name,
            COUNT(*) as num_records,
            SUM(dp.gross_pay) as total_gross,
            SUM(dp.base_wages) as total_base_wages,
            SUM(dp.gratuity_amount) as total_gratuity,
            SUM(dp.expenses) as total_expenses,
            SUM(dp.expense_reimbursement) as total_reimbursement,
            SUM(dp.hours_worked) as total_hours,
            SUM(dp.cpp) as total_cpp,
            SUM(dp.ei) as total_ei,
            SUM(dp.tax) as total_tax
        FROM driver_payroll dp
        JOIN employees e ON dp.employee_id = e.employee_id
        WHERE dp.year = 2012
        GROUP BY e.employee_id, e.full_name
        HAVING COUNT(*) > 0
        ORDER BY SUM(dp.gross_pay) DESC
    """)
    
    employees = cur.fetchall()
    
    print(f"\nFound {len(employees)} employees with 2012 payroll records\n")
    
    discrepancies = []
    
    for emp in employees:
        emp_id, full_name, num_records, total_gross, base_wages, gratuity, expenses, \
            reimbursement, hours, cpp, ei, tax = emp
        
        name_key = full_name.upper()
        
        if name_key in cra_data:
            cra = cra_data[name_key]
            
            # Calculate differences
            gross_diff = float(cra['box_14']) - float(total_gross or 0)
            cpp_diff = float(cra['box_16']) - float(cpp or 0)
            ei_diff = float(cra['box_18']) - float(ei or 0)
            tax_diff = float(cra['box_22']) - float(tax or 0)
            
            # Only show significant discrepancies (>$10)
            if abs(gross_diff) > 10:
                discrepancies.append({
                    'name': full_name,
                    'records': num_records,
                    'cra_gross': float(cra['box_14']),
                    'db_gross': float(total_gross or 0),
                    'gross_diff': gross_diff,
                    'base_wages': float(base_wages or 0),
                    'gratuity': float(gratuity or 0),
                    'expenses': float(expenses or 0),
                    'reimbursement': float(reimbursement or 0),
                    'hours': float(hours or 0),
                    'cra_cpp': float(cra['box_16']),
                    'db_cpp': float(cpp or 0),
                    'cpp_diff': cpp_diff,
                    'cra_ei': float(cra['box_18']),
                    'db_ei': float(ei or 0),
                    'ei_diff': ei_diff,
                    'cra_tax': float(cra['box_22']),
                    'db_tax': float(tax or 0),
                    'tax_diff': tax_diff
                })
    
    # Sort by largest gross difference
    discrepancies.sort(key=lambda x: abs(x['gross_diff']), reverse=True)
    
    print("TOP 10 DISCREPANCIES (CRA T4 vs Database):")
    print("-" * 80)
    
    for i, disc in enumerate(discrepancies[:10], 1):
        print(f"\n{i}. {disc['name']} ({disc['records']} payroll records)")
        print(f"   CRA Box 14 (Income):  ${disc['cra_gross']:>10,.2f}")
        print(f"   DB Gross Pay:         ${disc['db_gross']:>10,.2f}")
        print(f"   Missing:              ${disc['gross_diff']:>10,.2f} ({disc['gross_diff']/disc['cra_gross']*100:.1f}%)")
        
        print(f"\n   Database Components:")
        print(f"     Base Wages:         ${disc['base_wages']:>10,.2f}")
        print(f"     Gratuity:           ${disc['gratuity']:>10,.2f}")
        print(f"     Expenses:           ${disc['expenses']:>10,.2f}")
        print(f"     Reimbursement:      ${disc['reimbursement']:>10,.2f}")
        print(f"     Hours Worked:       {disc['hours']:>10,.1f}")
        
        print(f"\n   Deductions Comparison:")
        print(f"     CPP:  CRA ${disc['cra_cpp']:>8,.2f}  DB ${disc['db_cpp']:>8,.2f}  Diff ${disc['cpp_diff']:>8,.2f}")
        print(f"     EI:   CRA ${disc['cra_ei']:>8,.2f}  DB ${disc['db_ei']:>8,.2f}  Diff ${disc['ei_diff']:>8,.2f}")
        print(f"     Tax:  CRA ${disc['cra_tax']:>8,.2f}  DB ${disc['db_tax']:>8,.2f}  Diff ${disc['tax_diff']:>8,.2f}")
    
    # Summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY ANALYSIS")
    print("=" * 80)
    
    total_missing_gross = sum(d['gross_diff'] for d in discrepancies)
    employees_with_null_gratuity = sum(1 for d in discrepancies if d['gratuity'] == 0)
    employees_with_null_base = sum(1 for d in discrepancies if d['base_wages'] == 0)
    employees_with_no_hours = sum(1 for d in discrepancies if d['hours'] == 0)
    
    print(f"\nTotal employees with discrepancies: {len(discrepancies)}")
    print(f"Total missing gross income: ${total_missing_gross:,.2f}")
    print(f"\nPotential Data Quality Issues:")
    print(f"  - Employees with $0 gratuity: {employees_with_null_gratuity}/{len(discrepancies)}")
    print(f"  - Employees with $0 base wages: {employees_with_null_base}/{len(discrepancies)}")
    print(f"  - Employees with 0 hours: {employees_with_no_hours}/{len(discrepancies)}")
    
    # Check column population rates
    print("\n" + "=" * 80)
    print("DATABASE FIELD POPULATION ANALYSIS")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_records,
            COUNT(gross_pay) as has_gross_pay,
            COUNT(base_wages) as has_base_wages,
            COUNT(gratuity_amount) as has_gratuity,
            COUNT(expenses) as has_expenses,
            COUNT(expense_reimbursement) as has_reimbursement,
            COUNT(hours_worked) as has_hours,
            SUM(CASE WHEN gross_pay IS NOT NULL AND gross_pay > 0 THEN 1 ELSE 0 END) as gross_pay_nonzero,
            SUM(CASE WHEN base_wages IS NOT NULL AND base_wages > 0 THEN 1 ELSE 0 END) as base_wages_nonzero,
            SUM(CASE WHEN gratuity_amount IS NOT NULL AND gratuity_amount > 0 THEN 1 ELSE 0 END) as gratuity_nonzero,
            SUM(CASE WHEN hours_worked IS NOT NULL AND hours_worked > 0 THEN 1 ELSE 0 END) as hours_nonzero
        FROM driver_payroll
        WHERE year = 2012
    """)
    
    stats = cur.fetchone()
    total = stats[0]
    
    print(f"\nOut of {total} total 2012 payroll records:")
    print(f"  gross_pay populated: {stats[1]} ({stats[1]/total*100:.1f}%), non-zero: {stats[7]} ({stats[7]/total*100:.1f}%)")
    print(f"  base_wages populated: {stats[2]} ({stats[2]/total*100:.1f}%), non-zero: {stats[8]} ({stats[8]/total*100:.1f}%)")
    print(f"  gratuity_amount populated: {stats[3]} ({stats[3]/total*100:.1f}%), non-zero: {stats[9]} ({stats[9]/total*100:.1f}%)")
    print(f"  expenses populated: {stats[4]} ({stats[4]/total*100:.1f}%)")
    print(f"  expense_reimbursement populated: {stats[5]} ({stats[5]/total*100:.1f}%)")
    print(f"  hours_worked populated: {stats[6]} ({stats[6]/total*100:.1f}%), non-zero: {stats[10]} ({stats[10]/total*100:.1f}%)")
    
    # Recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    print("\n1. DATA IMPORT ISSUES:")
    print("   - Database has incomplete payroll records")
    print("   - gross_pay totals are significantly less than CRA T4 Box 14")
    print("   - Missing payroll periods or partial imports")
    
    print("\n2. FIELD MAPPING ISSUES:")
    if stats[8] < total * 0.5:
        print("   [WARN]  base_wages is mostly empty - may need to populate from gross_pay")
    if stats[9] < total * 0.1:
        print("   [WARN]  gratuity_amount is mostly empty - tips/gratuity not captured")
    if stats[10] < total * 0.5:
        print("   [WARN]  hours_worked is mostly empty - hour tracking incomplete")
    
    print("\n3. SUGGESTED FIXES:")
    print("   a) Import missing 2012 payroll data from other sources")
    print("   b) If base_wages is empty, populate from gross_pay field")
    print("   c) Check if gratuity is embedded in gross_pay or needs separate import")
    print("   d) Verify gross_pay = base_wages + gratuity_amount + expenses formula")
    print("   e) Review source data files for 2012 to identify missing records")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
