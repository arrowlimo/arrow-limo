#!/usr/bin/env python3
"""
Comprehensive Audit Verification for 2012-2014 - FIXED VERSION
Confirms all revenue matching, expenditure tracking, receipt reconciliation,
payroll alignment, GST calculations, and identifies discrepancies.

FIXES:
- banking_transactions: vendor_extracted (NOT vendor_name)
- receipts: vendor_name (confirmed correct)
- driver_payroll: numeric fields for COALESCE (NOT text)
- charters: total_amount_due, paid_amount (confirmed correct)
- payments: amount, payment_date (confirmed correct)
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
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def verify_table_columns(cur):
    """Verify actual column names in critical tables"""
    print("🔍 VERIFYING DATABASE SCHEMA")
    print("=" * 50)
    
    tables_to_check = [
        'charters', 'payments', 'receipts', 
        'banking_transactions', 'driver_payroll'
    ]
    
    schema_info = {}
    for table in tables_to_check:
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = %s 
            ORDER BY ordinal_position
        """, (table,))
        
        columns = {row[0]: row[1] for row in cur.fetchall()}
        schema_info[table] = columns
        print(f"\n{table.upper()}: {len(columns)} columns")
        
        # Show key columns we'll be using
        key_columns = {
            'charters': ['charter_id', 'total_amount_due', 'paid_amount', 'payment_status', 'charter_date'],
            'payments': ['payment_id', 'amount', 'payment_date', 'charter_id', 'reserve_number'],
            'receipts': ['id', 'vendor_name', 'gross_amount', 'gst_amount', 'receipt_date'],
            'banking_transactions': ['transaction_id', 'vendor_extracted', 'debit_amount', 'credit_amount', 'transaction_date'],
            'driver_payroll': ['id', 'driver_id', 'employee_id', 'gross_pay', 'cpp', 'ei', 'tax', 'net_pay', 'year']
        }
        
        for col in key_columns.get(table, []):
            status = "✓" if col in columns else "✗ MISSING"
            data_type = columns.get(col, 'N/A')
            print(f"  {status} {col} ({data_type})")
    
    return schema_info

def audit_charter_revenue_matching(cur, year):
    """Audit charter revenue vs payment matching for specific year"""
    print(f"\n📊 CHARTER REVENUE AUDIT - {year}")
    print("=" * 50)
    
    # Charter revenue summary - using confirmed column names
    cur.execute("""
        SELECT 
            COUNT(*) as charter_count,
            SUM(COALESCE(total_amount_due, 0)) as total_charter_revenue,
            SUM(COALESCE(paid_amount, 0)) as total_paid_amount,
            COUNT(CASE WHEN payment_status = 'paid' THEN 1 END) as paid_charters,
            COUNT(CASE WHEN payment_status = 'unpaid' OR payment_status IS NULL THEN 1 END) as unpaid_charters,
            SUM(COALESCE(rate, 0)) as total_base_rates,
            AVG(COALESCE(total_amount_due, 0)) as avg_charter_value
        FROM charters 
        WHERE EXTRACT(YEAR FROM charter_date) = %s
    """, (year,))
    
    charter_stats = cur.fetchone()
    
    # Payment collections for same year - using confirmed column names  
    cur.execute("""
        SELECT 
            COUNT(*) as payment_count,
            SUM(COALESCE(amount, 0)) as total_payments,
            COUNT(DISTINCT reserve_number) as unique_reserves_paid,
            COUNT(CASE WHEN charter_id IS NOT NULL THEN 1 END) as linked_to_charters,
            AVG(COALESCE(amount, 0)) as avg_payment_amount
        FROM payments 
        WHERE EXTRACT(YEAR FROM payment_date) = %s
    """, (year,))
    
    payment_stats = cur.fetchone()
    
    # Charter-payment linkage analysis
    cur.execute("""
        SELECT 
            COUNT(DISTINCT c.charter_id) as charters_with_payments,
            COUNT(DISTINCT p.payment_id) as payments_with_charters
        FROM charters c
        LEFT JOIN payments p ON p.charter_id = c.charter_id
        WHERE EXTRACT(YEAR FROM c.charter_date) = %s
    """, (year,))
    
    linkage_stats = cur.fetchone()
    
    # Revenue matching analysis
    charter_revenue = charter_stats[1] if charter_stats[1] else Decimal('0')
    payment_collections = payment_stats[1] if payment_stats[1] else Decimal('0')
    revenue_variance = charter_revenue - payment_collections
    variance_pct = (float(revenue_variance) / float(charter_revenue) * 100) if charter_revenue > 0 else 0
    
    results = {
        'year': year,
        'charter_count': charter_stats[0],
        'charter_revenue': float(charter_revenue),
        'charter_paid_amount': float(charter_stats[2]) if charter_stats[2] else 0,
        'payment_collections': float(payment_collections),
        'revenue_variance': float(revenue_variance),
        'variance_percentage': variance_pct,
        'paid_charters': charter_stats[3],
        'unpaid_charters': charter_stats[4],
        'base_rates_total': float(charter_stats[5]) if charter_stats[5] else 0,
        'avg_charter_value': float(charter_stats[6]) if charter_stats[6] else 0,
        'payment_count': payment_stats[0],
        'avg_payment_amount': float(payment_stats[4]) if payment_stats[4] else 0,
        'charter_payment_linkage': payment_stats[3] / payment_stats[0] * 100 if payment_stats[0] > 0 else 0,
        'charters_with_payments': linkage_stats[0],
        'payments_with_charters': linkage_stats[1],
        'status': 'PASS' if abs(variance_pct) < 10 else 'CRITICAL_VARIANCE'
    }
    
    print(f"Charters: {results['charter_count']:,} (${results['charter_revenue']:,.2f} revenue)")
    print(f"Charter Paid Amount: ${results['charter_paid_amount']:,.2f}")
    print(f"Payment Collections: ${results['payment_collections']:,.2f}")
    print(f"Revenue Variance: ${results['revenue_variance']:,.2f} ({results['variance_percentage']:.1f}%)")
    print(f"Base Rates Total: ${results['base_rates_total']:,.2f}")
    print(f"Charter-Payment Linkage: {results['charter_payment_linkage']:.1f}%")
    print(f"Charters with Payments: {results['charters_with_payments']:,}")
    print(f"Payments with Charters: {results['payments_with_charters']:,}")
    print(f"Status: {results['status']}")
    
    return results

def audit_expenditure_matching(cur, year):
    """Audit business expenditures and receipt matching - FIXED column names"""
    print(f"\n💸 EXPENDITURE AUDIT - {year}")
    print("=" * 40)
    
    # Receipt expenses - using confirmed column names
    cur.execute("""
        SELECT 
            COUNT(*) as receipt_count,
            SUM(COALESCE(gross_amount, 0)) as total_receipts,
            SUM(COALESCE(gst_amount, 0)) as total_gst,
            COUNT(CASE WHEN vendor_name IS NOT NULL AND vendor_name != '' THEN 1 END) as receipts_with_vendors,
            COUNT(CASE WHEN category IS NOT NULL AND category != '' THEN 1 END) as categorized_receipts,
            COUNT(DISTINCT vendor_name) as unique_vendors
        FROM receipts 
        WHERE EXTRACT(YEAR FROM receipt_date) = %s
    """, (year,))
    
    receipt_stats = cur.fetchone()
    
    # Banking expenses (debits) - FIXED: use vendor_extracted not vendor_name
    cur.execute("""
        SELECT 
            COUNT(*) as debit_count,
            SUM(COALESCE(debit_amount, 0)) as total_debits,
            COUNT(CASE WHEN vendor_extracted IS NOT NULL AND vendor_extracted != '' THEN 1 END) as debits_with_vendors,
            COUNT(DISTINCT vendor_extracted) as unique_banking_vendors
        FROM banking_transactions 
        WHERE EXTRACT(YEAR FROM transaction_date) = %s 
        AND debit_amount > 0
    """, (year,))
    
    banking_stats = cur.fetchone()
    
    # Banking credits (income verification)
    cur.execute("""
        SELECT 
            COUNT(*) as credit_count,
            SUM(COALESCE(credit_amount, 0)) as total_credits
        FROM banking_transactions 
        WHERE EXTRACT(YEAR FROM transaction_date) = %s 
        AND credit_amount > 0
    """, (year,))
    
    banking_credits = cur.fetchone()
    
    # Receipt-banking reconciliation
    cur.execute("""
        SELECT 
            COUNT(*) as receipts_linked_to_banking
        FROM receipts r
        INNER JOIN banking_transactions bt ON r.id = bt.receipt_id
        WHERE EXTRACT(YEAR FROM r.receipt_date) = %s
    """, (year,))
    
    reconciliation_stats = cur.fetchone()
    
    results = {
        'year': year,
        'receipt_count': receipt_stats[0],
        'receipt_total': float(receipt_stats[1]) if receipt_stats[1] else 0,
        'receipt_gst': float(receipt_stats[2]) if receipt_stats[2] else 0,
        'vendor_completion': receipt_stats[3] / receipt_stats[0] * 100 if receipt_stats[0] > 0 else 0,
        'categorization_completion': receipt_stats[4] / receipt_stats[0] * 100 if receipt_stats[0] > 0 else 0,
        'unique_vendors': receipt_stats[5],
        'banking_debits': float(banking_stats[1]) if banking_stats[1] else 0,
        'banking_debit_count': banking_stats[0],
        'banking_vendor_completion': banking_stats[2] / banking_stats[0] * 100 if banking_stats[0] > 0 else 0,
        'unique_banking_vendors': banking_stats[3],
        'banking_credits': float(banking_credits[1]) if banking_credits[1] else 0,
        'receipts_linked_to_banking': reconciliation_stats[0],
        'receipt_banking_linkage': reconciliation_stats[0] / receipt_stats[0] * 100 if receipt_stats[0] > 0 else 0,
        'status': 'PASS' if receipt_stats[0] > 0 else 'NO_RECEIPTS'
    }
    
    print(f"Receipts: {results['receipt_count']:,} (${results['receipt_total']:,.2f})")
    print(f"GST on Receipts: ${results['receipt_gst']:,.2f}")
    print(f"Vendor Completion: {results['vendor_completion']:.1f}% ({results['unique_vendors']} unique)")
    print(f"Categorization: {results['categorization_completion']:.1f}%")
    print(f"Banking Debits: {results['banking_debit_count']:,} (${results['banking_debits']:,.2f})")
    print(f"Banking Credits: ${results['banking_credits']:,.2f}")
    print(f"Banking Vendor Completion: {results['banking_vendor_completion']:.1f}%")
    print(f"Receipt-Banking Links: {results['receipts_linked_to_banking']:,} ({results['receipt_banking_linkage']:.1f}%)")
    print(f"Status: {results['status']}")
    
    return results

def audit_payroll_matching(cur, year):
    """Audit payroll records and T4 compliance - FIXED data type issues"""
    print(f"\n👥 PAYROLL AUDIT - {year}")
    print("=" * 35)
    
    # Driver payroll summary - FIXED: proper handling of numeric vs text fields
    cur.execute("""
        SELECT 
            COUNT(*) as payroll_entries,
            COUNT(DISTINCT COALESCE(driver_id, '')) + COUNT(DISTINCT employee_id) as unique_employees,
            SUM(COALESCE(gross_pay, 0)) as total_gross,
            SUM(COALESCE(cpp, 0)) as total_cpp,
            SUM(COALESCE(ei, 0)) as total_ei,
            SUM(COALESCE(tax, 0)) as total_tax,
            SUM(COALESCE(net_pay, 0)) as total_net,
            COUNT(CASE WHEN employee_id IS NOT NULL THEN 1 END) as entries_with_employee_id,
            COUNT(CASE WHEN driver_id IS NOT NULL AND driver_id != '' THEN 1 END) as entries_with_driver_id
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
    
    # T4 summary data
    cur.execute("""
        SELECT 
            SUM(COALESCE(t4_box_14, 0)) as t4_employment_income,
            SUM(COALESCE(t4_box_16, 0)) as t4_cpp_contributions,
            SUM(COALESCE(t4_box_18, 0)) as t4_ei_contributions,
            SUM(COALESCE(t4_box_22, 0)) as t4_income_tax,
            COUNT(CASE WHEN t4_box_14 > 0 THEN 1 END) as entries_with_t4_data
        FROM driver_payroll 
        WHERE year = %s
    """, (year,))
    
    t4_stats = cur.fetchone()
    
    # Calculate payroll tax compliance (rough estimates)
    gross_pay = payroll_stats[2] if payroll_stats[2] else Decimal('0')
    
    # CPP/EI rates vary by year - using approximate rates
    cpp_rates = {2012: 0.0495, 2013: 0.0495, 2014: 0.0495}
    ei_rates = {2012: 0.0183, 2013: 0.0188, 2014: 0.0178}
    
    expected_cpp = gross_pay * Decimal(str(cpp_rates.get(year, 0.0495)))
    expected_ei = gross_pay * Decimal(str(ei_rates.get(year, 0.0183)))
    
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
        'entries_with_employee_id': payroll_stats[7],
        'entries_with_driver_id': payroll_stats[8],
        'charters_with_drivers': charter_driver_stats[0],
        'unique_charter_drivers': charter_driver_stats[1],
        't4_employment_income': float(t4_stats[0]) if t4_stats[0] else 0,
        't4_cpp_contributions': float(t4_stats[1]) if t4_stats[1] else 0,
        't4_ei_contributions': float(t4_stats[2]) if t4_stats[2] else 0,
        't4_income_tax': float(t4_stats[3]) if t4_stats[3] else 0,
        'entries_with_t4_data': t4_stats[4],
        'expected_cpp': float(expected_cpp),
        'expected_ei': float(expected_ei),
        'cpp_compliance': abs(float(actual_cpp - expected_cpp)) < 1000,
        'ei_compliance': abs(float(actual_ei - expected_ei)) < 1000,
        'employee_id_linkage': payroll_stats[7] / payroll_stats[0] * 100 if payroll_stats[0] > 0 else 0,
        'status': 'PASS' if payroll_stats[0] > 0 else 'NO_PAYROLL'
    }
    
    print(f"Payroll Entries: {results['payroll_entries']:,}")
    print(f"Unique Employees: {results['unique_employees']:,}")
    print(f"Gross Pay: ${results['gross_pay']:,.2f}")
    print(f"CPP Withheld: ${results['cpp_withheld']:,.2f} (Expected: ${results['expected_cpp']:,.2f})")
    print(f"EI Withheld: ${results['ei_withheld']:,.2f} (Expected: ${results['expected_ei']:,.2f})")
    print(f"Tax Withheld: ${results['tax_withheld']:,.2f}")
    print(f"Net Pay: ${results['net_pay']:,.2f}")
    print(f"Employee ID Linkage: {results['employee_id_linkage']:.1f}%")
    print(f"T4 Employment Income: ${results['t4_employment_income']:,.2f}")
    print(f"Entries with T4 Data: {results['entries_with_t4_data']:,}")
    print(f"Charters with Drivers: {results['charters_with_drivers']:,}")
    print(f"Status: {results['status']}")
    
    return results

def audit_gst_calculations(cur, year):
    """Audit GST calculations and compliance - ENHANCED"""
    print(f"\n💰 GST AUDIT - {year}")
    print("=" * 30)
    
    # GST collected (from charter revenue)
    cur.execute("""
        SELECT 
            COUNT(*) as charters_count,
            SUM(COALESCE(total_amount_due, 0)) as gross_charter_revenue,
            SUM(COALESCE(total_amount_due, 0) * 0.05 / 1.05) as estimated_gst_collected
        FROM charters 
        WHERE EXTRACT(YEAR FROM charter_date) = %s
        AND total_amount_due > 0
    """, (year,))
    
    gst_collected_stats = cur.fetchone()
    
    # GST paid (from receipts)  
    cur.execute("""
        SELECT 
            COUNT(*) as receipt_count,
            SUM(COALESCE(gross_amount, 0)) as total_expenses,
            SUM(COALESCE(gst_amount, 0)) as recorded_gst_paid,
            SUM(COALESCE(gross_amount, 0) * 0.05 / 1.05) as estimated_gst_paid,
            COUNT(CASE WHEN gst_amount > 0 THEN 1 END) as receipts_with_gst
        FROM receipts 
        WHERE EXTRACT(YEAR FROM receipt_date) = %s
        AND gross_amount > 0
    """, (year,))
    
    gst_paid_stats = cur.fetchone()
    
    # Banking income verification (GST source)
    cur.execute("""
        SELECT 
            SUM(COALESCE(credit_amount, 0)) as banking_credits
        FROM banking_transactions 
        WHERE EXTRACT(YEAR FROM transaction_date) = %s 
        AND credit_amount > 0
    """, (year,))
    
    banking_income = cur.fetchone()
    
    # Calculate GST position
    estimated_gst_collected = gst_collected_stats[2] if gst_collected_stats[2] else Decimal('0')
    recorded_gst_paid = gst_paid_stats[2] if gst_paid_stats[2] else Decimal('0')
    estimated_gst_paid = gst_paid_stats[3] if gst_paid_stats[3] else Decimal('0')
    
    net_gst_owing = estimated_gst_collected - estimated_gst_paid
    
    # Safe float conversion with null handling
    charter_revenue_amount = float(gst_collected_stats[1]) if gst_collected_stats[1] else 0
    banking_credits_amount = float(banking_income[0]) if banking_income[0] else 0
    
    results = {
        'year': year,
        'charters_with_revenue': gst_collected_stats[0],
        'gross_charter_revenue': charter_revenue_amount,
        'estimated_gst_collected': float(estimated_gst_collected),
        'total_expenses': float(gst_paid_stats[1]) if gst_paid_stats[1] else 0,
        'recorded_gst_paid': float(recorded_gst_paid),
        'estimated_gst_paid': float(estimated_gst_paid),
        'receipts_with_gst': gst_paid_stats[4],
        'gst_recording_completion': gst_paid_stats[4] / gst_paid_stats[0] * 100 if gst_paid_stats[0] > 0 else 0,
        'net_gst_owing': float(net_gst_owing),
        'banking_credits': banking_credits_amount,
        'revenue_reconciliation': 'PASS' if abs(charter_revenue_amount - banking_credits_amount) < 10000 else 'VARIANCE',
        'status': 'GST_OWING' if net_gst_owing > 1000 else 'GST_REFUND' if net_gst_owing < -1000 else 'BALANCED'
    }
    
    print(f"Charter Revenue: ${results['gross_charter_revenue']:,.2f}")
    print(f"Estimated GST Collected: ${results['estimated_gst_collected']:,.2f}")
    print(f"Total Expenses: ${results['total_expenses']:,.2f}")
    print(f"Recorded GST Paid: ${results['recorded_gst_paid']:,.2f}")
    print(f"Estimated GST Paid: ${results['estimated_gst_paid']:,.2f}")
    print(f"GST Recording Completion: {results['gst_recording_completion']:.1f}%")
    print(f"Net GST Position: ${results['net_gst_owing']:,.2f} {'OWING' if results['net_gst_owing'] > 0 else 'REFUND'}")
    print(f"Banking Credits: ${results['banking_credits']:,.2f}")
    print(f"Revenue Reconciliation: {results['revenue_reconciliation']}")
    print(f"Status: {results['status']}")
    
    return results

def identify_discrepancies(audit_results):
    """Identify critical discrepancies and issues requiring attention"""
    print(f"\n🚨 DISCREPANCY ANALYSIS")
    print("=" * 50)
    
    issues = []
    critical_issues = []
    
    for year_data in audit_results:
        year = year_data['year']
        
        # Revenue variance issues
        if abs(year_data['revenue']['revenue_variance']) > 10000:
            critical_issues.append({
                'year': year,
                'category': 'REVENUE_VARIANCE',
                'severity': 'CRITICAL',
                'amount': year_data['revenue']['revenue_variance'],
                'description': f"${year_data['revenue']['revenue_variance']:,.2f} variance between charter revenue and payment collections",
                'impact': 'Revenue recognition accuracy'
            })
        
        # Payment linkage issues
        if year_data['revenue']['charter_payment_linkage'] < 75:
            issues.append({
                'year': year,
                'category': 'PAYMENT_LINKAGE',
                'severity': 'HIGH',
                'percentage': year_data['revenue']['charter_payment_linkage'],
                'description': f"Only {year_data['revenue']['charter_payment_linkage']:.1f}% of payments linked to charters",
                'impact': 'Revenue tracking completeness'
            })
        
        # GST compliance issues
        if year_data['gst']['net_gst_owing'] > 10000:
            critical_issues.append({
                'year': year,
                'category': 'GST_LIABILITY',
                'severity': 'CRITICAL',
                'amount': year_data['gst']['net_gst_owing'],
                'description': f"${year_data['gst']['net_gst_owing']:,.2f} GST owing to CRA",
                'impact': 'Tax compliance and penalties'
            })
        
        # Payroll employee linkage issues
        if year_data['payroll']['employee_id_linkage'] < 50:
            issues.append({
                'year': year,
                'category': 'PAYROLL_LINKAGE',
                'severity': 'MEDIUM',
                'percentage': year_data['payroll']['employee_id_linkage'],
                'description': f"Only {year_data['payroll']['employee_id_linkage']:.1f}% of payroll entries linked to employee records",
                'impact': 'Employee record tracking'
            })
        
        # Receipt completeness issues
        if year_data['expenditure']['vendor_completion'] < 90:
            issues.append({
                'year': year,
                'category': 'VENDOR_COMPLETION',
                'severity': 'MEDIUM',
                'percentage': year_data['expenditure']['vendor_completion'],
                'description': f"Only {year_data['expenditure']['vendor_completion']:.1f}% of receipts have vendor names",
                'impact': 'Expense categorization accuracy'
            })
    
    # Print summary
    print(f"CRITICAL ISSUES: {len(critical_issues)}")
    for issue in critical_issues:
        print(f"  [WARN]  {issue['year']}: {issue['description']} ({issue['severity']})")
    
    print(f"\nHIGH/MEDIUM ISSUES: {len(issues)}")
    for issue in issues:
        print(f"  ⚡ {issue['year']}: {issue['description']} ({issue['severity']})")
    
    return {
        'critical_issues': critical_issues,
        'other_issues': issues,
        'total_issues': len(critical_issues) + len(issues)
    }

def main():
    """Run comprehensive audit verification for 2012-2014"""
    print("🔍 COMPREHENSIVE AUDIT VERIFICATION 2012-2014 - FIXED VERSION")
    print("=" * 70)
    print("Verifying: Revenue matching, expenditure tracking, payroll compliance, GST calculations")
    print("Database: PostgreSQL almsdata")
    print("=" * 70)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Verify schema first
        schema_info = verify_table_columns(cur)
        
        audit_results = []
        
        for year in [2012, 2013, 2014]:
            print(f"\n{'='*20} YEAR {year} AUDIT {'='*20}")
            
            # Run all audit functions
            revenue_audit = audit_charter_revenue_matching(cur, year)
            expenditure_audit = audit_expenditure_matching(cur, year)  
            payroll_audit = audit_payroll_matching(cur, year)
            gst_audit = audit_gst_calculations(cur, year)
            
            year_results = {
                'year': year,
                'revenue': revenue_audit,
                'expenditure': expenditure_audit,
                'payroll': payroll_audit,
                'gst': gst_audit
            }
            
            audit_results.append(year_results)
        
        # Identify discrepancies across all years
        discrepancy_analysis = identify_discrepancies(audit_results)
        
        # Create comprehensive JSON report
        final_report = {
            'audit_timestamp': datetime.now().isoformat(),
            'audit_scope': '2012-2014 Comprehensive Business Data Verification',
            'database': 'PostgreSQL almsdata',
            'schema_verification': schema_info,
            'yearly_results': audit_results,
            'discrepancy_analysis': discrepancy_analysis,
            'summary': {
                'years_audited': len(audit_results),
                'total_issues_found': discrepancy_analysis['total_issues'],
                'critical_issues': len(discrepancy_analysis['critical_issues']),
                'audit_status': 'COMPLETE_WITH_ISSUES' if discrepancy_analysis['total_issues'] > 0 else 'CLEAN'
            }
        }
        
        # Save JSON report
        report_filename = f"comprehensive_audit_2012_2014_fixed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(final_report, f, indent=2, default=str)
        
        print(f"\n📄 AUDIT REPORT SAVED: {report_filename}")
        print(f"\n[OK] AUDIT COMPLETE")
        print(f"Issues Found: {discrepancy_analysis['total_issues']} ({len(discrepancy_analysis['critical_issues'])} critical)")
        
        return final_report
        
    except Exception as e:
        print(f"\n[FAIL] AUDIT ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()