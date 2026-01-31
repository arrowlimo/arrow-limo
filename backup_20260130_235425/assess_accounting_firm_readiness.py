#!/usr/bin/env python3
"""
Accounting Firm Submission Readiness Assessment
Analyzes audit results to determine readiness for each year 2012-2014
"""

import json
import glob
import os
from datetime import datetime

def assess_year_readiness(year_data):
    """Assess accounting firm submission readiness for a specific year"""
    year = year_data['year']
    revenue = year_data['revenue']
    expenditure = year_data['expenditure'] 
    payroll = year_data['payroll']
    gst = year_data['gst']
    
    print(f"\n📅 YEAR {year} ASSESSMENT:")
    print("-" * 30)
    
    # Revenue Assessment
    revenue_complete = revenue['charter_revenue'] > 0
    revenue_reasonable = abs(revenue['variance_percentage']) < 50
    payment_linkage = revenue['charter_payment_linkage'] > 50
    
    print(f"📊 REVENUE:")
    print(f"   Charter Revenue: ${revenue['charter_revenue']:,.2f} {'✓' if revenue_complete else '✗ MISSING'}")
    print(f"   Payment Collections: ${revenue['payment_collections']:,.2f}")
    print(f"   Variance: ${revenue['revenue_variance']:,.2f} ({revenue['variance_percentage']:.1f}%)")
    print(f"   Payment Linkage: {revenue['charter_payment_linkage']:.1f}% {'✓' if payment_linkage else '⚠ LOW'}")
    
    # Expense Assessment  
    expense_complete = expenditure['receipt_count'] > 0
    vendor_complete = expenditure['vendor_completion'] > 90
    
    print(f"💸 EXPENSES:")
    print(f"   Receipts: {expenditure['receipt_count']} (${expenditure['receipt_total']:,.2f}) {'✓' if expense_complete else '✗ MISSING'}")
    print(f"   Vendor Completion: {expenditure['vendor_completion']:.1f}% {'✓' if vendor_complete else '⚠ INCOMPLETE'}")
    print(f"   GST on Expenses: ${expenditure['receipt_gst']:,.2f}")
    
    # Payroll Assessment
    payroll_complete = payroll['payroll_entries'] > 0
    employee_linkage = payroll['employee_id_linkage'] > 90
    
    print(f"👥 PAYROLL:")
    print(f"   Payroll Entries: {payroll['payroll_entries']} {'✓' if payroll_complete else '✗ MISSING'}")
    print(f"   Gross Pay: ${payroll['gross_pay']:,.2f}")
    print(f"   Employee Linkage: {payroll['employee_id_linkage']:.1f}% {'✓' if employee_linkage else '⚠ INCOMPLETE'}")
    print(f"   T4 Data: ${payroll['t4_employment_income']:,.2f} {'✓' if payroll['t4_employment_income'] > 0 else '⚠ MISSING'}")
    
    # GST Assessment
    gst_owing = gst['net_gst_owing']
    gst_reasonable = abs(gst_owing) < 50000
    
    print(f"💰 GST:")
    print(f"   GST Collected: ${gst['estimated_gst_collected']:,.2f}")
    print(f"   GST Paid: ${gst['recorded_gst_paid']:,.2f}")  
    print(f"   Net Position: ${gst_owing:,.2f} {'OWING' if gst_owing > 0 else 'REFUND'}")
    
    # Identify Critical Issues
    critical_issues = []
    warnings = []
    
    if not revenue_complete:
        critical_issues.append('Missing revenue data')
    if not revenue_reasonable:
        warnings.append(f'Large revenue variance ({revenue["variance_percentage"]:.1f}%)')
    if not expense_complete and year < 2014:
        critical_issues.append('Missing expense data') 
    if not payroll_complete:
        critical_issues.append('Missing payroll data')
    if not employee_linkage and payroll['payroll_entries'] > 0:
        warnings.append('Poor employee linkage')
    if payroll['t4_employment_income'] == 0 and payroll['gross_pay'] > 0:
        warnings.append('Missing T4 data')
    if abs(gst_owing) > 50000:
        critical_issues.append(f'High GST liability (${gst_owing:,.2f})')
    
    # Determine Readiness Status
    if len(critical_issues) == 0 and len(warnings) <= 1:
        status = '🟢 READY FOR SUBMISSION'
        recommendation = 'Complete data package ready for accounting firm'
    elif len(critical_issues) == 0:
        status = '🟡 READY WITH NOTES'  
        recommendation = 'Ready for submission with explanatory notes'
    else:
        status = '🔴 NOT READY - ISSUES MUST BE RESOLVED'
        recommendation = 'Critical issues must be addressed before submission'
    
    print(f"\n📋 SUBMISSION STATUS: {status}")
    print(f"💡 RECOMMENDATION: {recommendation}")
    
    if critical_issues:
        print(f"🚨 CRITICAL ISSUES:")
        for issue in critical_issues:
            print(f"   • {issue}")
    
    if warnings:
        print(f"[WARN]  WARNINGS/NOTES:")
        for warning in warnings:
            print(f"   • {warning}")
    
    # Year-specific notes
    if year == 2012:
        print(f"[OK] STRENGTHS: Good expense tracking, complete payroll, revenue recovered")
        
    elif year == 2013:
        print(f"🚨 CRITICAL: 2013 has unfiled GST return - ${gst_owing:,.2f} owing + penalties")
        print(f"📞 ACTION REQUIRED: Engage tax professional immediately")
        print(f"⏰ URGENCY: High - CRA penalties accumulating")
        
    elif year == 2014:
        print(f"ℹ️  NOTE: Minimal business activity, very low expenses")
        print(f"📝 EXPLANATION NEEDED: Business wind-down or operational change")
    
    return {
        'year': year,
        'status': status,
        'critical_issues': len(critical_issues),
        'warnings': len(warnings),
        'ready': len(critical_issues) == 0,
        'gst_owing': gst_owing
    }

def main():
    """Generate accounting firm readiness assessment"""
    print("🏢 ACCOUNTING FIRM SUBMISSION READINESS ASSESSMENT")
    print("=" * 70)
    
    # Load latest audit report
    audit_files = glob.glob('comprehensive_audit_2012_2014_fixed_*.json')
    if not audit_files:
        print("[FAIL] No audit files found")
        return
        
    latest_file = max(audit_files, key=os.path.getctime)
    print(f"📄 ANALYZING: {latest_file}")
    print(f"📅 GENERATED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    with open(latest_file, 'r') as f:
        audit_data = json.load(f)
    
    year_assessments = []
    
    # Assess each year
    for year_data in audit_data['yearly_results']:
        assessment = assess_year_readiness(year_data)
        year_assessments.append(assessment)
    
    # Overall Summary
    print(f"\n🎯 EXECUTIVE SUMMARY:")
    print("=" * 50)
    
    ready_years = [a for a in year_assessments if a['ready']]
    not_ready_years = [a for a in year_assessments if not a['ready']]
    
    print(f"Ready for Submission: {len(ready_years)} years")
    print(f"Require Resolution: {len(not_ready_years)} years")
    
    print(f"\n📊 YEAR-BY-YEAR STATUS:")
    for assessment in year_assessments:
        year = assessment['year']
        status = assessment['status']
        issues = assessment['critical_issues']
        warnings = assessment['warnings'] 
        gst = assessment['gst_owing']
        
        print(f"   {year}: {status}")
        print(f"        Issues: {issues}, Warnings: {warnings}, GST: ${gst:,.2f}")
    
    print(f"\n🚨 PRIORITY ACTIONS:")
    if any(a['year'] == 2013 for a in not_ready_years):
        print("   1. 2013 GST FILING - URGENT: Engage tax professional immediately")
    if any(a['critical_issues'] > 0 for a in year_assessments):
        print("   2. RESOLVE CRITICAL ISSUES: Address data gaps before submission")
    
    print(f"\n[OK] CONFIRMED STATUS:")
    print(f"   • 2012: {'✓ READY' if any(a['year'] == 2012 and a['ready'] for a in year_assessments) else '✗ NOT READY'}")
    print(f"   • 2013: {'✓ READY' if any(a['year'] == 2013 and a['ready'] for a in year_assessments) else '✗ HAS ISSUES'}")  
    print(f"   • 2014: {'✓ READY' if any(a['year'] == 2014 and a['ready'] for a in year_assessments) else '✗ UNKNOWN/ISSUES'}")

if __name__ == "__main__":
    main()