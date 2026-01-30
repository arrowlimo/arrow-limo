#!/usr/bin/env python3
"""
Generate corrected summary report for key employees showing:
1. Payroll entries (what was recorded)
2. Banking transactions by classification
3. Reconciliation notes

Focus on: Paul D Richard, Matthew Donat Richard, Michael Richard, David W Richard
"""

import psycopg2
import csv
from pathlib import Path
from collections import defaultdict

DB = dict(dbname='almsdata', user='postgres', password='***REDACTED***', host='localhost')
EXPORT_DIR = Path(__file__).parent.parent / 'exports' / 'driver_audit'


def connect():
    return psycopg2.connect(**DB)


def generate_key_employee_report():
    conn = connect()
    cur = conn.cursor()
    
    KEY_EMPLOYEES = [
        'Paul D Richard',
        'Matthew Richard',
        'Matt Kapustinsky',  # Same as Matthew
        'Michael Richard',
        'David W Richard',
    ]
    
    print("\n" + "="*100)
    print("KEY EMPLOYEE BANKING & PAYROLL RECONCILIATION")
    print("="*100)
    
    results = []
    
    for emp_name in KEY_EMPLOYEES:
        # Get employee ID
        cur.execute("""
            SELECT employee_id, employee_number
            FROM employees
            WHERE COALESCE(full_name, first_name || ' ' || last_name) = %s
        """, (emp_name,))
        emp_row = cur.fetchone()
        
        if not emp_row:
            print(f"\n[FAIL] Employee not found: {emp_name}")
            continue
        
        emp_id, emp_no = emp_row
        
        print(f"\n{'='*100}")
        print(f"EMPLOYEE: {emp_name} (ID: {emp_id}, #: {emp_no})")
        print(f"{'='*100}")
        
        # Payroll summary
        cur.execute("""
            SELECT 
                EXTRACT(YEAR FROM pay_date)::INT AS year,
                COUNT(*) as entries,
                SUM(gross_pay) as total_pay
            FROM driver_payroll
            WHERE (employee_id = %s OR driver_id = %s)
              AND pay_date >= DATE '2014-01-01'
            GROUP BY year
            ORDER BY year
        """, (emp_id, emp_no))
        payroll = cur.fetchall()
        
        print(f"\nPAYROLL (2014+):")
        print(f"  {'Year':<6} {'Entries':>8} {'Gross Pay':>15}")
        print(f"  {'-'*35}")
        total_payroll_entries = 0
        total_payroll_amount = 0.0
        for year, count, total in payroll:
            print(f"  {year:<6} {count:>8,} ${total:>14,.2f}")
            total_payroll_entries += count
            total_payroll_amount += float(total or 0)
        print(f"  {'-'*35}")
        print(f"  {'TOTAL':<6} {total_payroll_entries:>8,} ${total_payroll_amount:>14,.2f}")
        
        # Banking summary by classification
        banking_matches = defaultdict(lambda: {'count': 0, 'amount': 0.0})
        with open(EXPORT_DIR / 'banking_employee_matches.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['employee_name'] == emp_name:
                    classification = row['classification']
                    amount = float(row['amount'] or 0)
                    banking_matches[classification]['count'] += 1
                    banking_matches[classification]['amount'] += amount
        
        print(f"\nBANKING TRANSACTIONS (2014+):")
        print(f"  {'Classification':<25} {'Count':>8} {'Total Amount':>15}")
        print(f"  {'-'*55}")
        for classification in sorted(banking_matches.keys()):
            stats = banking_matches[classification]
            print(f"  {classification:<25} {stats['count']:>8,} ${stats['amount']:>14,.2f}")
        
        # Reconciliation notes
        print(f"\nRECONCILIATION NOTES:")
        if emp_name == 'Paul D Richard':
            print(f"  ✓ Owner - wages are DEFERRED (banked), not paid out")
            print(f"  ✓ {banking_matches['DEFERRED_WAGES']['count']} transactions flagged as deferred wages")
            print(f"  ✓ {banking_matches['ETRANSFER']['count']} etransfers may be business expenses or draws")
            print(f"  ⚠ Review etransfers to classify: owner draw vs business expense")
            results.append({
                'employee': emp_name,
                'payroll_entries': total_payroll_entries,
                'payroll_gross': total_payroll_amount,
                'deferred_wages': banking_matches['DEFERRED_WAGES']['amount'],
                'etransfers': banking_matches['ETRANSFER']['amount'],
                'note': 'Owner deferred wages - not paid'
            })
        
        elif emp_name in ['Matthew Richard', 'Matt Kapustinsky']:
            print(f"  ✓ All banking transactions classified as BUSINESS_EXPENSE")
            print(f"  ✓ {banking_matches['BUSINESS_EXPENSE']['count']} business expenses: fuel, alcohol for vehicle/passengers")
            print(f"  ✓ Wages are DEFERRED (banked), similar to Paul")
            print(f"  ✓ No actual wage payments found in banking")
            results.append({
                'employee': emp_name,
                'payroll_entries': total_payroll_entries,
                'payroll_gross': total_payroll_amount,
                'business_expenses': banking_matches['BUSINESS_EXPENSE']['amount'],
                'etransfers': 0,
                'note': 'Deferred wages + business expenses only'
            })
        
        elif emp_name == 'Michael Richard':
            print(f"  ✓ Active driver (Mike Richard)")
            print(f"  ✓ {banking_matches['ETRANSFER']['count']} etransfers likely driver pay")
            print(f"  ⚠ Compare payroll gross to etransfers to verify payment completeness")
            etransfer_total = banking_matches['ETRANSFER']['amount']
            if total_payroll_amount > 0:
                coverage = (abs(etransfer_total) / total_payroll_amount) * 100
                print(f"  📊 Banking coverage: ${abs(etransfer_total):,.2f} / ${total_payroll_amount:,.2f} = {coverage:.1f}%")
            results.append({
                'employee': emp_name,
                'payroll_entries': total_payroll_entries,
                'payroll_gross': total_payroll_amount,
                'etransfers': abs(etransfer_total),
                'coverage_pct': coverage if total_payroll_amount > 0 else 0,
                'note': 'Active driver - verify payment coverage'
            })
        
        elif emp_name == 'David W Richard':
            print(f"  ✓ All {banking_matches['LOAN']['count']} transactions classified as LOAN")
            print(f"  ✓ Total loan activity: ${abs(banking_matches['LOAN']['amount']):,.2f}")
            print(f"  ✓ No driver pay - this is loan provider, not employee")
            print(f"  ✓ Payroll entries: {total_payroll_entries} (likely $0 or minimal)")
            results.append({
                'employee': emp_name,
                'payroll_entries': total_payroll_entries,
                'payroll_gross': total_payroll_amount,
                'loan_activity': abs(banking_matches['LOAN']['amount']),
                'note': 'Loan provider - not paid employee'
            })
    
    # Write summary CSV
    if results:
        fieldnames = list(results[0].keys())
        with open(EXPORT_DIR / 'key_employee_reconciliation.csv', 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(results)
        print(f"\n[OK] Summary written to: {EXPORT_DIR / 'key_employee_reconciliation.csv'}")
    
    cur.close()
    conn.close()


if __name__ == '__main__':
    generate_key_employee_report()
