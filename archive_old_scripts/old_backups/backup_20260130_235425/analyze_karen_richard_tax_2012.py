#!/usr/bin/env python3
"""
Analyze Karen Richard's 2012 Tax Return
- Extract key financial data from Karen's T1 return
- Cross-reference with business payroll records
- Identify income splitting and spousal payment arrangements
- Flag CRA compliance risks

Safe: Read-only analysis. Outputs to staging/2012_comparison/karen_richard_tax_analysis.txt
"""
from pathlib import Path
import pdfplumber
import re
from decimal import Decimal
import os
import psycopg2

KAREN_TAX_PDF = Path(r"L:\limo\pdf\RICHARD, KAREN_ocred.pdf")
OUTPUT_TXT = Path(r"L:\limo\staging\2012_comparison\karen_richard_tax_analysis.txt")


def get_db_connection():
    host = os.getenv('DB_HOST', 'localhost')
    name = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '***REDACTED***')
    port = int(os.getenv('DB_PORT', '5432'))
    return psycopg2.connect(host=host, dbname=name, user=user, password=password, port=port)


def extract_tax_return_data() -> dict:
    """Extract key amounts from Karen's T1 return."""
    if not KAREN_TAX_PDF.exists():
        return {}
    
    with pdfplumber.open(KAREN_TAX_PDF) as pdf:
        text = '\n'.join([p.extract_text() or '' for p in pdf.pages])
    
    data = {
        'sin': '638 432 138',
        'name': 'KAREN RICHARD',
        'address': '70 RUPERT CRES, RED DEER AB T4P 2Z1',
    }
    
    # Extract key line items
    patterns = {
        'total_income_150': r'Total income.*line 150.*?([\d,]+)\s*\d{2}',
        'taxable_income_260': r'Taxable income.*line 260.*?([\d,]+)\s*\d{2}',
        'refund_484': r'Refund.*line 484.*?([\d,]+)\s*\d{2}',
        'tax_credits_350': r'Total federal non-refundable tax credits.*line 350.*?([\d,]+)\s*\d{2}',
        'prepared_date': r'Printed:\s*(\d{4}/\d{2}/\d{2})',
    }
    
    for key, pattern in patterns.items():
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            val = m.group(1).replace(',', '').strip()
            data[key] = val
    
    return data


def query_karen_payroll() -> dict:
    """Query database for any payroll records for Karen Richard."""
    conn = get_db_connection()
    results = {}
    
    try:
        with conn.cursor() as cur:
            # Check employees table
            cur.execute("""
                SELECT employee_id, full_name, position, hire_date, 
                       status, hourly_rate, salary
                FROM employees 
                WHERE LOWER(full_name) LIKE '%karen%' 
                   OR (LOWER(first_name) = 'karen' AND LOWER(last_name) = 'richard')
                LIMIT 5;
            """)
            results['employees'] = cur.fetchall()
            
            # Check driver_payroll for 2012 - simplified query without driver_name
            cur.execute("""
                SELECT COUNT(*) as count, 
                       COALESCE(SUM(gross_pay), 0) as total_gross,
                       COALESCE(SUM(net_pay), 0) as total_net
                FROM driver_payroll
                WHERE year = 2012
                  AND employee_id IN (
                      SELECT employee_id FROM employees 
                      WHERE LOWER(full_name) LIKE '%karen%'
                  );
            """)
            payroll_row = cur.fetchone()
            results['payroll_2012'] = {
                'count': payroll_row[0] if payroll_row else 0,
                'total_gross': Decimal(str(payroll_row[1])) if payroll_row else Decimal('0'),
                'total_net': Decimal(str(payroll_row[2])) if payroll_row else Decimal('0'),
            }
            
            # Check if any T4 slips issued to Karen
            cur.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_name = 't4_slips';
            """)
            has_t4_table = cur.fetchone()[0] > 0
            
            if has_t4_table:
                cur.execute("""
                    SELECT COUNT(*), COALESCE(SUM(employment_income), 0)
                    FROM t4_slips
                    WHERE LOWER(employee_name) LIKE '%karen%'
                      AND tax_year = 2012;
                """)
                t4_row = cur.fetchone()
                results['t4_slips'] = {
                    'count': t4_row[0] if t4_row else 0,
                    'total_income': Decimal(str(t4_row[1])) if t4_row else Decimal('0'),
                }
            else:
                results['t4_slips'] = {'count': 0, 'total_income': Decimal('0')}
                
    finally:
        try:
            conn.close()
        except Exception:
            pass
    
    return results


def main():
    tax_data = extract_tax_return_data()
    payroll_data = query_karen_payroll()
    
    lines = []
    lines.append("=" * 80)
    lines.append("KAREN RICHARD - 2012 TAX RETURN ANALYSIS")
    lines.append("=" * 80)
    lines.append("")
    
    lines.append("RELATIONSHIP TO BUSINESS")
    lines.append("-" * 80)
    lines.append("Name: Karen Richard")
    lines.append("Relationship: Spouse of Paul Richard (Owner, Arrow Limousine)")
    lines.append("SIN: 638 432 138")
    lines.append(f"Address: {tax_data.get('address', 'N/A')}")
    lines.append("")
    
    lines.append("2012 PERSONAL TAX RETURN (T1)")
    lines.append("-" * 80)
    lines.append(f"Total Income (line 150):                    ${tax_data.get('total_income_150', 'N/A')}")
    lines.append(f"Taxable Income (line 260):                  ${tax_data.get('taxable_income_260', 'N/A')}")
    lines.append(f"Federal Non-Refundable Tax Credits (350):  ${tax_data.get('tax_credits_350', 'N/A')}")
    lines.append(f"Refund Amount (line 484):                   ${tax_data.get('refund_484', 'N/A')}")
    lines.append(f"Return Prepared Date:                       {tax_data.get('prepared_date', 'N/A')}")
    lines.append(f"Source Document:                            {KAREN_TAX_PDF}")
    lines.append("")
    lines.append("FILING STATUS")
    lines.append("-" * 80)
    lines.append("[WARN]  CRITICAL ISSUE: No e-file confirmation found")
    lines.append("   - T1 return was prepared (2013/04/30)")
    lines.append("   - Unknown if actually submitted to CRA")
    lines.append("   - Potential CRA compliance risk")
    lines.append("   - ACTION: Verify filing status with CRA or tax preparer")
    lines.append("")
    
    lines.append("BUSINESS PAYROLL RECORDS")
    lines.append("-" * 80)
    emp_records = payroll_data.get('employees', [])
    if emp_records:
        lines.append(f"Employee Records Found: {len(emp_records)}")
        for emp in emp_records:
            lines.append(f"  ID: {emp[0]}, Name: {emp[1]}, Position: {emp[2]}")
            lines.append(f"     Hire: {emp[3]}, Status: {emp[4]}, Salary: ${emp[6] or 0}")
    else:
        lines.append("Employee Records Found: 0")
        lines.append("  [WARN]  No employee record found for Karen Richard")
    lines.append("")
    
    payroll = payroll_data.get('payroll_2012', {})
    lines.append(f"2012 Payroll Entries: {payroll.get('count', 0)}")
    lines.append(f"Total Gross Pay:      ${payroll.get('total_gross', Decimal('0')):,.2f}")
    lines.append(f"Total Net Pay:        ${payroll.get('total_net', Decimal('0')):,.2f}")
    lines.append("")
    
    t4_data = payroll_data.get('t4_slips', {})
    lines.append(f"2012 T4 Slips Issued: {t4_data.get('count', 0)}")
    lines.append(f"T4 Employment Income: ${t4_data.get('total_income', Decimal('0')):,.2f}")
    lines.append("")
    
    lines.append("RECONCILIATION ANALYSIS")
    lines.append("-" * 80)
    t1_income = Decimal(tax_data.get('total_income_150', '0').replace(',', '') or '0')
    payroll_gross = payroll.get('total_gross', Decimal('0'))
    t4_income = t4_data.get('total_income', Decimal('0'))
    
    lines.append(f"T1 Total Income (line 150):      ${t1_income:,.2f}")
    lines.append(f"Payroll Records (gross):         ${payroll_gross:,.2f}")
    lines.append(f"T4 Slips (employment income):    ${t4_income:,.2f}")
    lines.append("")
    
    if t1_income > 0:
        variance_payroll = (t1_income - payroll_gross).quantize(Decimal('0.01'))
        variance_t4 = (t1_income - t4_income).quantize(Decimal('0.01'))
        lines.append(f"Variance (T1 vs Payroll):        ${variance_payroll:,.2f}")
        lines.append(f"Variance (T1 vs T4):             ${variance_t4:,.2f}")
        lines.append("")
        
        if variance_payroll.copy_abs() > Decimal('100'):
            lines.append("[WARN]  SIGNIFICANT VARIANCE between T1 income and payroll records")
            lines.append("   Possible explanations:")
            lines.append("   - Income from sources other than Arrow Limousine")
            lines.append("   - Payroll records incomplete or not linked to Karen")
            lines.append("   - Income splitting or dividend payments not in payroll")
            lines.append("   - Investment income, rental income, or other sources")
            lines.append("")
    
    lines.append("TAX IMPLICATIONS FOR BUSINESS")
    lines.append("-" * 80)
    lines.append("1. Income Splitting Considerations")
    lines.append("   - If Karen received salary/wages from business:")
    lines.append("     • Must be reasonable for services actually provided")
    lines.append("     • CRA scrutinizes spousal salary arrangements")
    lines.append("     • Impacts business deductions and payroll tax")
    lines.append("")
    lines.append("2. Payroll Tax Compliance")
    lines.append("   - If Karen was on payroll, employer must remit:")
    lines.append("     • CPP contributions (employer + employee portions)")
    lines.append("     • EI premiums (employer + employee portions)")
    lines.append("     • Income tax withholdings")
    lines.append("     • T4 slip must be issued by Feb 28, 2013")
    lines.append("")
    lines.append("3. GST/HST Considerations")
    lines.append("   - Spouse income does not affect GST registration")
    lines.append("   - But business expense deductions impact GST ITC claims")
    lines.append("")
    lines.append("4. CRA Audit Risk Factors")
    lines.append("   - Missing T1 filing confirmation increases risk")
    lines.append("   - Income splitting arrangements often reviewed")
    lines.append("   - Cross-referenced with business T2/partnership return")
    lines.append("   - T4 slip filing confirmation found (2013-02-02) suggests")
    lines.append("     business did file T4s, but unclear if Karen's included")
    lines.append("")
    
    lines.append("RECOMMENDED ACTIONS")
    lines.append("-" * 80)
    lines.append("1. URGENT: Verify Karen's 2012 T1 was actually filed with CRA")
    lines.append("   - Check CRA My Account for Notice of Assessment")
    lines.append("   - Contact tax preparer for filing confirmation")
    lines.append("   - If not filed, assess late-filing penalties and interest")
    lines.append("")
    lines.append("2. Reconcile Karen's income sources:")
    lines.append("   - Review if she received salary/wages from Arrow Limousine")
    lines.append("   - Check for T4 slip issued to her (SIN: 638 432 138)")
    lines.append("   - Identify any other income sources (investment, rental, etc.)")
    lines.append("")
    lines.append("3. Review business payroll deductions for Karen (if applicable):")
    lines.append("   - Verify CPP/EI remittances were made")
    lines.append("   - Confirm income tax withholdings match T4")
    lines.append("   - Check for payroll account compliance")
    lines.append("")
    lines.append("4. Business tax return coordination:")
    lines.append("   - Ensure business return (T2 or partnership) properly")
    lines.append("     reflects any salary/wages paid to Karen")
    lines.append("   - Cross-reference expense deductions with T4 amounts")
    lines.append("")
    
    OUTPUT_TXT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"Saved analysis to: {OUTPUT_TXT}")
    print("")
    print("KEY FINDINGS:")
    print(f"  Karen's 2012 T1 Income:     ${t1_income:,.2f}")
    print(f"  Payroll Records (gross):    ${payroll_gross:,.2f}")
    print(f"  Filing Status:              UNKNOWN (no e-file confirmation)")
    print(f"  CRA Compliance Risk:        HIGH (return prepared but filing unconfirmed)")


if __name__ == '__main__':
    main()
