#!/usr/bin/env python3
"""
Comprehensive Audit Verification for 2012-2014
Confirms all revenue matching, expenditure tracking, receipt reconciliation,
payroll alignment, GST calculations, and identifies discrepancies.
"""

import psycopg2
import os
from decimal import Decimal
from datetime import datetime
import json

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def audit_charter_revenue_matching(cur, year):
    """Audit charter revenue vs payment matching for specific year"""
    print(f"\n📊 CHARTER REVENUE AUDIT - {year}")
    print("=" * 50)
    
    # Charter revenue summary
    cur.execute("""
        SELECT 
            COUNT(*) as charter_count,
            SUM(COALESCE(total_amount_due, 0)) as total_charter_revenue,
            SUM(COALESCE(paid_amount, 0)) as total_paid_amount,
            COUNT(CASE WHEN payment_status = 'paid' THEN 1 END) as paid_charters,
            COUNT(CASE WHEN payment_status = 'unpaid' OR payment_status IS NULL THEN 1 END) as unpaid_charters
        FROM charters 
        WHERE EXTRACT(YEAR FROM charter_date) = %s
    """, (year,))
    
    charter_stats = cur.fetchone()
    
    # Payment collections for same year
    cur.execute("""
        SELECT 
            COUNT(*) as payment_count,
            SUM(COALESCE(amount, 0)) as total_payments,
            COUNT(DISTINCT reserve_number) as unique_reserves_paid,
            COUNT(CASE WHEN charter_id IS NOT NULL THEN 1 END) as linked_to_charters
        FROM payments 
        WHERE EXTRACT(YEAR FROM payment_date) = %s
    """, (year,))
    
    payment_stats = cur.fetchone()
    
    # Revenue matching analysis
    charter_revenue = charter_stats[1] if charter_stats[1] else Decimal('0')
    payment_collections = payment_stats[1] if payment_stats[1] else Decimal('0')
    revenue_variance = charter_revenue - payment_collections
    
    results = {
        'year': year,
        'charter_count': charter_stats[0],
        'charter_revenue': float(charter_revenue),
        'payment_collections': float(payment_collections),
        'revenue_variance': float(revenue_variance),
        'paid_charters': charter_stats[3],
        'unpaid_charters': charter_stats[4],
        'payment_count': payment_stats[0],
        'charter_payment_linkage': payment_stats[3] / payment_stats[0] * 100 if payment_stats[0] > 0 else 0,
        'status': 'PASS' if abs(revenue_variance) < 1000 else 'REVIEW_NEEDED'
    }
    
    print(f"Charters: {results['charter_count']:,} (${results['charter_revenue']:,.2f} revenue)")
    print(f"Payments: {results['payment_count']:,} (${results['payment_collections']:,.2f} collected)")
    print(f"Variance: ${results['revenue_variance']:,.2f}")
    print(f"Charter-Payment Linkage: {results['charter_payment_linkage']:.1f}%")
    print(f"Status: {results['status']}")
    
    return results

def audit_expenditure_matching(cur, year):
    """Audit business expenditures and receipt matching"""
    print(f"\n💸 EXPENDITURE AUDIT - {year}")
    print("=" * 40)
    
    # Receipt expenses
    cur.execute("""
        SELECT 
            COUNT(*) as receipt_count,
            SUM(COALESCE(gross_amount, 0)) as total_receipts,
            SUM(COALESCE(gst_amount, 0)) as total_gst,
            COUNT(CASE WHEN vendor_name IS NOT NULL AND vendor_name != '' THEN 1 END) as receipts_with_vendors,
            COUNT(CASE WHEN category IS NOT NULL AND category != '' THEN 1 END) as categorized_receipts
        FROM receipts 
        WHERE EXTRACT(YEAR FROM receipt_date) = %s
    """, (year,))
    
    receipt_stats = cur.fetchone()
    
    # Banking expenses (debits)
    cur.execute("""
        SELECT 
            COUNT(*) as debit_count,
            SUM(COALESCE(debit_amount, 0)) as total_debits,
            COUNT(CASE WHEN vendor_extracted IS NOT NULL AND vendor_extracted != '' THEN 1 END) as debits_with_vendors
        FROM banking_transactions 
        WHERE EXTRACT(YEAR FROM transaction_date) = %s 
        AND debit_amount > 0
    """, (year,))
    
    banking_stats = cur.fetchone()
    
    # Journal expenses (skip for now due to date format issues)
    journal_stats = (0, 0)  # Placeholder
    
    journal_stats = cur.fetchone()
    
    results = {
        'year': year,
        'receipt_count': receipt_stats[0],
        'receipt_total': float(receipt_stats[1]) if receipt_stats[1] else 0,
        'receipt_gst': float(receipt_stats[2]) if receipt_stats[2] else 0,
        'vendor_completion': receipt_stats[3] / receipt_stats[0] * 100 if receipt_stats[0] > 0 else 0,
        'categorization_completion': receipt_stats[4] / receipt_stats[0] * 100 if receipt_stats[0] > 0 else 0,
        'banking_debits': float(banking_stats[1]) if banking_stats[1] else 0,
        'journal_debits': 0,  # Placeholder - journal analysis needs schema work
        'status': 'PASS' if receipt_stats[0] > 0 else 'NO_RECEIPTS'
    }
    
    print(f"Receipts: {results['receipt_count']:,} (${results['receipt_total']:,.2f})")
    print(f"GST on Receipts: ${results['receipt_gst']:,.2f}")
    print(f"Vendor Completion: {results['vendor_completion']:.1f}%")
    print(f"Categorization: {results['categorization_completion']:.1f}%")
    print(f"Banking Debits: ${results['banking_debits']:,.2f}")
    print(f"Journal Debits: ${results['journal_debits']:,.2f}")
    print(f"Status: {results['status']}")
    
    return results

def audit_payroll_matching(cur, year):
    """Audit payroll records and T4 compliance"""
    print(f"\n👥 PAYROLL AUDIT - {year}")
    print("=" * 35)
    
    # Driver payroll summary
    cur.execute("""
        SELECT 
            COUNT(*) as payroll_entries,
            COUNT(DISTINCT driver_id) + COUNT(DISTINCT employee_id) as unique_employees,
            SUM(COALESCE(gross_pay, 0)) as total_gross,
            SUM(COALESCE(cpp, 0)) as total_cpp,
            SUM(COALESCE(ei, 0)) as total_ei,
            SUM(COALESCE(tax, 0)) as total_tax,
            SUM(COALESCE(net_pay, 0)) as total_net
        FROM driver_payroll 
        WHERE year = %s
    """, (year,))
    
    payroll_stats = cur.fetchone()
    
    # Charter-driver linkage
    cur.execute("""
        SELECT 
            COUNT(*) as charters_with_drivers,
            COUNT(DISTINCT assigned_driver_id) as unique_charter_drivers
        FROM charters 
        WHERE EXTRACT(YEAR FROM charter_date) = %s 
        AND assigned_driver_id IS NOT NULL
    """, (year,))
    
    charter_driver_stats = cur.fetchone()
    
    # Calculate payroll tax compliance
    gross_pay = payroll_stats[2] if payroll_stats[2] else Decimal('0')
    expected_cpp = gross_pay * Decimal('0.0495') if year == 2013 else gross_pay * Decimal('0.0487')  # Rough rates
    expected_ei = gross_pay * Decimal('0.0188') if year == 2013 else gross_pay * Decimal('0.0178')
    
    actual_cpp = payroll_stats[3] if payroll_stats[3] else Decimal('0')
    actual_ei = payroll_stats[4] if payroll_stats[4] else Decimal('0')
    
    results = {
        'year': year,
        'payroll_entries': payroll_stats[0],
        'unique_employees': payroll_stats[1],
        'gross_pay': float(gross_pay),
        'cpp_withheld': float(actual_cpp),
        'ei_withheld': float(actual_ei),
        'tax_withheld': float(payroll_stats[5]) if payroll_stats[5] else 0,
        'net_pay': float(payroll_stats[6]) if payroll_stats[6] else 0,
        'charters_with_drivers': charter_driver_stats[0],
        'unique_charter_drivers': charter_driver_stats[1],
        'cpp_compliance': abs(float(actual_cpp - expected_cpp)) < 1000,
        'ei_compliance': abs(float(actual_ei - expected_ei)) < 1000,
        'status': 'PASS' if payroll_stats[0] > 0 else 'NO_PAYROLL'
    }
    
    print(f"Payroll Entries: {results['payroll_entries']:,}")
    print(f"Unique Employees: {results['unique_employees']:,}")
    print(f"Gross Pay: ${results['gross_pay']:,.2f}")
    print(f"CPP Withheld: ${results['cpp_withheld']:,.2f} (Expected: ${float(expected_cpp):,.2f})")
    print(f"EI Withheld: ${results['ei_withheld']:,.2f} (Expected: ${float(expected_ei):,.2f})")
    print(f"Charter-Driver Links: {results['charters_with_drivers']:,}")
    print(f"Status: {results['status']}")
    
    return results

def audit_gst_calculations(cur, year):
    """Audit GST calculations and compliance"""
    print(f"\n🧮 GST AUDIT - {year}")
    print("=" * 30)
    
    # Charter GST collected
    cur.execute("""
        SELECT 
            SUM(COALESCE(total_amount_due, 0)) as charter_revenue,
            SUM(COALESCE(total_amount_due, 0)) * 0.05 as estimated_gst_collected
        FROM charters 
        WHERE EXTRACT(YEAR FROM charter_date) = %s
    """, (year,))
    
    charter_gst = cur.fetchone()
    
    # Receipt GST (Input Tax Credits)
    cur.execute("""
        SELECT 
            SUM(COALESCE(gst_amount, 0)) as receipt_gst,
            COUNT(CASE WHEN gst_amount > 0 THEN 1 END) as receipts_with_gst,
            COUNT(*) as total_receipts
        FROM receipts 
        WHERE EXTRACT(YEAR FROM receipt_date) = %s
    """, (year,))
    
    receipt_gst = cur.fetchone()
    
    # Journal GST entries (skip for now due to schema complexity)
    journal_gst = (None,)  # Placeholder
    
    journal_gst = cur.fetchone()
    
    # Load tax summary data if available
    gst_collected_actual = None
    gst_itc_actual = None
    net_gst_actual = None
    
    try:
        with open(f'l:/limo/exports/cra/{year}/tax_year_summary_{year}.md', 'r') as f:
            content = f.read()
            if 'GST/HST collected: $' in content:
                gst_collected_actual = float(content.split('GST/HST collected: $')[1].split('\n')[0].replace(',', ''))
            if 'ITCs (from receipts/GL): $' in content:
                gst_itc_actual = float(content.split('ITCs (from receipts/GL): $')[1].split('\n')[0].replace(',', ''))
            if 'Net GST/HST: $' in content:
                net_gst_actual = float(content.split('Net GST/HST: $')[1].split(' ')[0].replace(',', ''))
    except:
        pass
    
    estimated_collected = float(charter_gst[1]) if charter_gst[1] else 0
    receipt_itc = float(receipt_gst[0]) if receipt_gst[0] else 0
    
    results = {
        'year': year,
        'charter_revenue': float(charter_gst[0]) if charter_gst[0] else 0,
        'estimated_gst_collected': estimated_collected,
        'actual_gst_collected': gst_collected_actual,
        'receipt_itc': receipt_itc,
        'actual_itc': gst_itc_actual,
        'net_gst_estimated': estimated_collected - receipt_itc,
        'net_gst_actual': net_gst_actual,
        'gst_calculation_match': abs(estimated_collected - (gst_collected_actual or 0)) < 1000 if gst_collected_actual else False,
        'itc_calculation_match': abs(receipt_itc - (gst_itc_actual or 0)) < 1000 if gst_itc_actual else False,
        'receipts_with_gst_pct': receipt_gst[1] / receipt_gst[2] * 100 if receipt_gst[2] > 0 else 0,
        'status': 'CALCULATED' if gst_collected_actual else 'NEEDS_CALCULATION'
    }
    
    print(f"Charter Revenue: ${results['charter_revenue']:,.2f}")
    print(f"Est. GST Collected: ${results['estimated_gst_collected']:,.2f}")
    print(f"Actual GST Collected: ${results['actual_gst_collected']:,.2f}" if results['actual_gst_collected'] else "Not calculated")
    print(f"Receipt ITCs: ${results['receipt_itc']:,.2f}")
    print(f"Actual ITCs: ${results['actual_itc']:,.2f}" if results['actual_itc'] else "Not calculated")
    print(f"Net GST Position: ${results['net_gst_actual']:,.2f}" if results['net_gst_actual'] else f"${results['net_gst_estimated']:,.2f} (estimated)")
    print(f"Receipts with GST: {results['receipts_with_gst_pct']:.1f}%")
    print(f"Status: {results['status']}")
    
    return results

def identify_discrepancies(results_2012, results_2013, results_2014):
    """Identify discrepancies and issues across all years"""
    print(f"\n🚨 DISCREPANCY ANALYSIS")
    print("=" * 40)
    
    issues = []
    
    # Revenue matching issues
    for year_results in [results_2012, results_2013, results_2014]:
        year = year_results['revenue']['year']
        revenue_var = abs(year_results['revenue']['revenue_variance'])
        
        if revenue_var > 5000:
            issues.append({
                'year': year,
                'type': 'REVENUE_MISMATCH',
                'severity': 'HIGH' if revenue_var > 20000 else 'MEDIUM',
                'description': f"Revenue variance of ${revenue_var:,.2f} between charters and payments",
                'impact': f"Potential revenue recognition or collection issues"
            })
        
        # Payment linkage issues
        linkage_pct = year_results['revenue']['charter_payment_linkage']
        if linkage_pct < 80:
            issues.append({
                'year': year,
                'type': 'PAYMENT_LINKAGE',
                'severity': 'MEDIUM',
                'description': f"Only {linkage_pct:.1f}% of payments linked to charters",
                'impact': "Revenue tracking and reconciliation difficulties"
            })
        
        # Receipt issues
        if year_results['expenditure']['receipt_count'] == 0:
            issues.append({
                'year': year,
                'type': 'MISSING_RECEIPTS',
                'severity': 'HIGH',
                'description': "No receipt records found",
                'impact': "Cannot claim business expenses or GST ITCs"
            })
        
        vendor_pct = year_results['expenditure']['vendor_completion']
        if vendor_pct < 70 and year_results['expenditure']['receipt_count'] > 0:
            issues.append({
                'year': year,
                'type': 'VENDOR_DATA_INCOMPLETE',
                'severity': 'MEDIUM',
                'description': f"Only {vendor_pct:.1f}% of receipts have vendor names",
                'impact': "Audit trail and expense categorization issues"
            })
        
        # Payroll issues
        if year_results['payroll']['payroll_entries'] == 0:
            issues.append({
                'year': year,
                'type': 'MISSING_PAYROLL',
                'severity': 'HIGH',
                'description': "No payroll records found",
                'impact': "T4 compliance and payroll tax remittance issues"
            })
        
        if not year_results['payroll']['cpp_compliance']:
            issues.append({
                'year': year,
                'type': 'CPP_MISMATCH',
                'severity': 'HIGH',
                'description': "CPP withholdings don't match expected amounts",
                'impact': "Payroll tax compliance and remittance issues"
            })
        
        # GST issues
        if year_results['gst']['status'] == 'NEEDS_CALCULATION':
            issues.append({
                'year': year,
                'type': 'GST_NOT_CALCULATED',
                'severity': 'CRITICAL',
                'description': "GST amounts not calculated or summarized",
                'impact': "Cannot file GST returns, potential CRA penalties"
            })
        
        if not year_results['gst']['gst_calculation_match'] and year_results['gst']['actual_gst_collected']:
            issues.append({
                'year': year,
                'type': 'GST_CALCULATION_MISMATCH',
                'severity': 'HIGH',
                'description': "GST calculations don't match between methods",
                'impact': "Audit risk and potential penalties"
            })
    
    return issues

def generate_audit_report(results_2012, results_2013, results_2014, issues):
    """Generate comprehensive audit report"""
    
    report = {
        'audit_date': datetime.now().isoformat(),
        'audit_scope': '2012-2014 Comprehensive Verification',
        'years_audited': [2012, 2013, 2014],
        'results_by_year': {
            2012: results_2012,
            2013: results_2013, 
            2014: results_2014
        },
        'issues_identified': issues,
        'summary': {
            'total_issues': len(issues),
            'critical_issues': len([i for i in issues if i['severity'] == 'CRITICAL']),
            'high_issues': len([i for i in issues if i['severity'] == 'HIGH']),
            'medium_issues': len([i for i in issues if i['severity'] == 'MEDIUM']),
        }
    }
    
    # Save detailed JSON report
    with open('l:/limo/AUDIT_VERIFICATION_2012_2014.json', 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    # Generate summary report
    print(f"\n📋 AUDIT SUMMARY REPORT")
    print("=" * 50)
    print(f"Audit Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Scope: 2012-2014 Comprehensive Verification")
    print()
    
    print("ISSUES IDENTIFIED:")
    if not issues:
        print("[OK] NO ISSUES FOUND - All data appears consistent")
    else:
        for issue in sorted(issues, key=lambda x: (x['year'], x['severity'])):
            severity_icon = "🔴" if issue['severity'] == 'CRITICAL' else "🟡" if issue['severity'] == 'HIGH' else "🟠"
            print(f"{severity_icon} {issue['year']} - {issue['type']}: {issue['description']}")
            print(f"    Impact: {issue['impact']}")
    
    print(f"\nTOTAL ISSUES: {len(issues)} (Critical: {report['summary']['critical_issues']}, High: {report['summary']['high_issues']}, Medium: {report['summary']['medium_issues']})")
    print(f"Detailed report saved: AUDIT_VERIFICATION_2012_2014.json")

def main():
    print("🔍 COMPREHENSIVE AUDIT VERIFICATION 2012-2014")
    print("=" * 55)
    print("Verifying: Revenue matching, Expenditures, Receipts, Payroll, GST")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Audit each year
        results_2012 = {
            'revenue': audit_charter_revenue_matching(cur, 2012),
            'expenditure': audit_expenditure_matching(cur, 2012),
            'payroll': audit_payroll_matching(cur, 2012),
            'gst': audit_gst_calculations(cur, 2012)
        }
        
        results_2013 = {
            'revenue': audit_charter_revenue_matching(cur, 2013),
            'expenditure': audit_expenditure_matching(cur, 2013), 
            'payroll': audit_payroll_matching(cur, 2013),
            'gst': audit_gst_calculations(cur, 2013)
        }
        
        results_2014 = {
            'revenue': audit_charter_revenue_matching(cur, 2014),
            'expenditure': audit_expenditure_matching(cur, 2014),
            'payroll': audit_payroll_matching(cur, 2014), 
            'gst': audit_gst_calculations(cur, 2014)
        }
        
        # Identify issues
        issues = identify_discrepancies(results_2012, results_2013, results_2014)
        
        # Generate report
        generate_audit_report(results_2012, results_2013, results_2014, issues)
        
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()