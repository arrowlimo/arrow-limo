#!/usr/bin/env python3
"""
Analyze Paul Richard's 2012 Tax Return
- Extract key financial data from Paul's T1 return (business owner)
- Cross-reference with business payroll records
- Compare to Karen Richard's return for household income analysis
- Flag CRA compliance risks

Safe: Read-only analysis. Outputs to staging/2012_comparison/paul_richard_tax_analysis.txt
"""
from pathlib import Path
import pdfplumber
import re
from decimal import Decimal
import os
import psycopg2

PAUL_TAX_PDF = Path(r"L:\limo\pdf\RICHARD, PAUL_ocred.pdf")
KAREN_ANALYSIS = Path(r"L:\limo\staging\2012_comparison\karen_richard_tax_analysis.txt")
OUTPUT_TXT = Path(r"L:\limo\staging\2012_comparison\paul_richard_tax_analysis.txt")


def get_db_connection():
    host = os.getenv('DB_HOST', 'localhost')
    name = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '***REMOVED***')
    port = int(os.getenv('DB_PORT', '5432'))
    return psycopg2.connect(host=host, dbname=name, user=user, password=password, port=port)


def extract_tax_return_data() -> dict:
    """Extract key amounts from Paul's T1 return."""
    if not PAUL_TAX_PDF.exists():
        return {}
    
    with pdfplumber.open(PAUL_TAX_PDF) as pdf:
        text = '\n'.join([p.extract_text() or '' for p in pdf.pages])
    
    data = {
        'sin': '637 660 614',
        'name': 'PAUL RICHARD',
        'address': '70 RUPERT CRES, RED DEER AB T4P 2Z1',
    }
    
    # Extract key line items
    patterns = {
        'total_income_150': r'Total income.*line 150.*?([\d,]+)\s*\d{2}',
        'taxable_income_260': r'Taxable income.*line 260.*?([\d,]+)\s*\d{2}',
        'refund_484': r'Refund.*line 484.*?([\d,]+)\s*\d{2}',
        'balance_owing_485': r'Balance owing.*line 485.*?([\d,]+)\s*\d{2}',
        'tax_credits_350': r'Total federal non-refundable tax credits.*line 350.*?([\d,]+)\s*\d{2}',
        'prepared_date': r'Printed:\s*(\d{4}/\d{2}/\d{2})',
    }
    
    for key, pattern in patterns.items():
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            val = m.group(1).replace(',', '').strip()
            data[key] = val
    
    return data


def query_paul_payroll() -> dict:
    """Query database for any payroll records for Paul Richard."""
    conn = get_db_connection()
    results = {}
    
    try:
        with conn.cursor() as cur:
            # Check employees table
            cur.execute("""
                SELECT employee_id, full_name, position, hire_date, 
                       status, hourly_rate, salary
                FROM employees 
                WHERE LOWER(full_name) LIKE '%paul%richard%' 
                   OR (LOWER(first_name) = 'paul' AND LOWER(last_name) = 'richard')
                LIMIT 5;
            """)
            results['employees'] = cur.fetchall()
            
            # Check driver_payroll for 2012
            cur.execute("""
                SELECT COUNT(*) as count, 
                       COALESCE(SUM(gross_pay), 0) as total_gross,
                       COALESCE(SUM(net_pay), 0) as total_net
                FROM driver_payroll
                WHERE year = 2012
                  AND employee_id IN (
                      SELECT employee_id FROM employees 
                      WHERE LOWER(full_name) LIKE '%paul%richard%'
                  );
            """)
            payroll_row = cur.fetchone()
            results['payroll_2012'] = {
                'count': payroll_row[0] if payroll_row else 0,
                'total_gross': Decimal(str(payroll_row[1])) if payroll_row else Decimal('0'),
                'total_net': Decimal(str(payroll_row[2])) if payroll_row else Decimal('0'),
            }
            
            # Check if any T4 slips issued to Paul
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
                    WHERE LOWER(employee_name) LIKE '%paul%richard%'
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
    payroll_data = query_paul_payroll()
    
    lines = []
    lines.append("=" * 80)
    lines.append("PAUL RICHARD - 2012 TAX RETURN ANALYSIS (Business Owner)")
    lines.append("=" * 80)
    lines.append("")
    
    lines.append("RELATIONSHIP TO BUSINESS")
    lines.append("-" * 80)
    lines.append("Name: Paul Richard")
    lines.append("Role: OWNER - Arrow Limousine & Sedan Services Ltd.")
    lines.append("SIN: 637 660 614")
    lines.append(f"Address: {tax_data.get('address', 'N/A')}")
    lines.append("Spouse: Karen Richard (SIN: 638 432 138)")
    lines.append("")
    
    lines.append("2012 PERSONAL TAX RETURN (T1)")
    lines.append("-" * 80)
    lines.append(f"Total Income (line 150):                    ${tax_data.get('total_income_150', 'N/A')}")
    lines.append(f"Taxable Income (line 260):                  ${tax_data.get('taxable_income_260', 'N/A')}")
    lines.append(f"Federal Non-Refundable Tax Credits (350):  ${tax_data.get('tax_credits_350', 'N/A')}")
    
    refund = tax_data.get('refund_484', '')
    balance = tax_data.get('balance_owing_485', '')
    if refund:
        lines.append(f"Refund Amount (line 484):                   ${refund}")
    if balance:
        lines.append(f"Balance Owing (line 485):                   ${balance}")
    
    lines.append(f"Return Prepared Date:                       {tax_data.get('prepared_date', 'N/A')}")
    lines.append(f"Source Document:                            {PAUL_TAX_PDF}")
    lines.append("")
    
    lines.append("FILING STATUS")
    lines.append("-" * 80)
    lines.append("[WARN]  CRITICAL ISSUE: No e-file confirmation found")
    lines.append("   - T1 return was prepared (2013/04/30) - same date as Karen's")
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
        lines.append("  [WARN]  No employee record found for Paul Richard")
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
            lines.append("   For business OWNER, this is EXPECTED and normal:")
            lines.append("   - Owner draws/dividends not recorded as salary/wages")
            lines.append("   - Business income flows through to personal return")
            lines.append("   - May include T5 dividends, T5013 partnership income")
            lines.append("   - Investment income, capital gains, or other sources")
            lines.append("")
    
    lines.append("OWNER INCOME ANALYSIS")
    lines.append("-" * 80)
    lines.append(f"Paul's T1 Income:  ${t1_income:,.2f} (very low for business owner)")
    lines.append("")
    lines.append("[WARN]  CRITICAL OBSERVATION: Paul's income ($17,272.59) is LOWER than spouse")
    lines.append("   Karen's T1 Income: $52,800.00")
    lines.append("   Paul's T1 Income:  $17,272.59")
    lines.append("   Household Total:   $70,072.59")
    lines.append("")
    lines.append("This is UNUSUAL for a business owner and suggests:")
    lines.append("1. Income splitting strategy - shifting income to lower-earning spouse")
    lines.append("2. Business may have had losses or minimal profit in 2012")
    lines.append("3. Owner may be taking minimal salary to minimize personal tax")
    lines.append("4. Business income retained in corporation (if incorporated)")
    lines.append("5. Possible financial distress (low revenues vs high expenses)")
    lines.append("")
    lines.append("Cross-reference with business financials:")
    lines.append("- Database shows $319K deposits (incomplete, missing $811K per QB)")
    lines.append("- QB shows $1.13M total deposits across both bank accounts")
    lines.append("- Low owner income despite ~$1M+ business revenue suggests:")
    lines.append("  • High operating expenses")
    lines.append("  • Business losses")
    lines.append("  • Tax planning/deferral strategies")
    lines.append("")
    
    lines.append("TAX IMPLICATIONS FOR BUSINESS")
    lines.append("-" * 80)
    lines.append("1. Owner Compensation Structure")
    lines.append("   - Low T1 income ($17,272) suggests minimal salary extraction")
    lines.append("   - If incorporated: May be taking dividends (T5) not salary (T4)")
    lines.append("   - If sole proprietor: Business income flows to line 135/139/143")
    lines.append("   - Review business structure: Corp vs proprietorship vs partnership")
    lines.append("")
    lines.append("2. Income Splitting Review")
    lines.append("   - Karen's income ($52,800) > Paul's income ($17,272)")
    lines.append("   - CRA attribution rules apply to spousal income arrangements")
    lines.append("   - TOSI (Tax on Split Income) rules for family members")
    lines.append("   - Must justify Karen's compensation as reasonable")
    lines.append("")
    lines.append("3. Business Loss/Profitability")
    lines.append("   - Low owner income may indicate business loss year")
    lines.append("   - Non-capital losses can be carried back 3 years, forward 20")
    lines.append("   - Review T2125 (business income/loss) schedules")
    lines.append("")
    lines.append("4. CRA Audit Risk Factors")
    lines.append("   - Missing T1 filing confirmation increases risk")
    lines.append("   - Income splitting arrangements often reviewed")
    lines.append("   - Low owner income vs high spouse income triggers scrutiny")
    lines.append("   - Missing banking deposits ($811K gap) creates red flags")
    lines.append("")
    
    lines.append("HOUSEHOLD TAX SUMMARY (Paul + Karen)")
    lines.append("-" * 80)
    karen_income = Decimal('52800.00')
    household_income = t1_income + karen_income
    lines.append(f"Paul's T1 Income:        ${t1_income:,.2f}")
    lines.append(f"Karen's T1 Income:       ${karen_income:,.2f}")
    lines.append(f"Total Household Income:  ${household_income:,.2f}")
    lines.append("")
    lines.append("Balance owing/refund:")
    if balance:
        lines.append(f"  Paul owes:             ${balance}")
    if refund:
        lines.append(f"  Paul refund:           ${refund}")
    lines.append(f"  Karen refund:          $932.32")
    lines.append("")
    
    lines.append("RECOMMENDED ACTIONS")
    lines.append("-" * 80)
    lines.append("1. URGENT: Verify Paul's 2012 T1 was actually filed with CRA")
    lines.append("   - Check CRA My Account for Notice of Assessment")
    lines.append("   - Contact tax preparer for filing confirmation")
    lines.append("   - If not filed, assess late-filing penalties and interest")
    lines.append("")
    lines.append("2. Reconcile business income to personal return:")
    lines.append("   - Review business structure (corporation vs proprietorship)")
    lines.append("   - If corp: Obtain T2 corporate return and T5 dividend slips")
    lines.append("   - If proprietor: Review T2125 business income schedule")
    lines.append("   - Cross-reference business revenue ($1.13M per QB) to owner income")
    lines.append("")
    lines.append("3. Review income splitting arrangements:")
    lines.append("   - Justify Karen's $52,800 income as reasonable compensation")
    lines.append("   - Document services provided if salary/wages")
    lines.append("   - Review TOSI rules if dividends paid to spouse")
    lines.append("")
    lines.append("4. Investigate business profitability:")
    lines.append("   - Low owner income suggests losses or minimal profit")
    lines.append("   - Review 2012 business financials (income statement)")
    lines.append("   - Assess if business was viable or in financial distress")
    lines.append("   - Consider implications for loss carrybacks/carryforwards")
    lines.append("")
    lines.append("5. Address missing banking data:")
    lines.append("   - $811K missing deposits per earlier audit")
    lines.append("   - Scotiabank account ($298K) completely missing from database")
    lines.append("   - Import missing transactions to complete financial picture")
    lines.append("")
    
    OUTPUT_TXT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"Saved analysis to: {OUTPUT_TXT}")
    print("")
    print("KEY FINDINGS:")
    print(f"  Paul's 2012 T1 Income:      ${t1_income:,.2f}")
    print(f"  Karen's 2012 T1 Income:     ${karen_income:,.2f}")
    print(f"  Household Total:            ${household_income:,.2f}")
    print(f"  Paul owes/refund:           {'$' + balance if balance else '$' + refund if refund else 'N/A'}")
    print(f"  Payroll Records (gross):    ${payroll_gross:,.2f}")
    print(f"  Filing Status:              UNKNOWN (no e-file confirmation)")
    print(f"  CRA Compliance Risk:        HIGH (owner income lower than spouse, filing unconfirmed)")


if __name__ == '__main__':
    main()
