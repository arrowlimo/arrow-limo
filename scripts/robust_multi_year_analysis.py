#!/usr/bin/env python3
"""
Robust Multi-Year Analysis: 2013-2015
=====================================

Simple, reliable analysis focusing on the key 2012 patterns:
- High non-payroll cash indicating missing business expenses
- Limited receipt data suggesting accountant record gaps  
- Tax implications of missing deductions

Author: AI Agent  
Date: October 2025
"""

import psycopg2
from decimal import Decimal

def analyze_year_simple(year):
    """Simple, robust analysis for a single year."""
    
    conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
    cur = conn.cursor()
    
    print(f"\n📅 YEAR {year} ANALYSIS")
    print("=" * 25)
    
    # Payroll totals
    cur.execute("SELECT COUNT(*), SUM(gross_pay), SUM(net_pay) FROM driver_payroll WHERE year = %s", (year,))
    payroll_result = cur.fetchone()
    payroll_count = payroll_result[0] if payroll_result else 0
    payroll_gross = float(payroll_result[1]) if payroll_result and payroll_result[1] else 0
    payroll_net = float(payroll_result[2]) if payroll_result and payroll_result[2] else 0
    
    print(f"👥 Payroll: {payroll_count:,} entries, ${payroll_gross:,.0f} gross, ${payroll_net:,.0f} net")
    
    # Banking cash withdrawals  
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(debit_amount), 0) 
        FROM banking_transactions 
        WHERE EXTRACT(YEAR FROM transaction_date) = %s 
          AND debit_amount > 0 
          AND (description ILIKE %s OR description ILIKE %s)
    """, (year, '%cash%', '%withdrawal%'))
    
    cash_result = cur.fetchone()
    cash_count = cash_result[0] if cash_result else 0
    cash_total = float(cash_result[1]) if cash_result and cash_result[1] else 0
    
    print(f"💰 Cash Withdrawals: {cash_count} transactions, ${cash_total:,.0f}")
    
    # Calculate non-payroll cash (key 2012 indicator)
    non_payroll_cash = cash_total - payroll_net
    non_payroll_pct = (non_payroll_cash / cash_total * 100) if cash_total > 0 else 0
    
    print(f"🏢 Non-Payroll Cash: ${non_payroll_cash:,.0f} ({non_payroll_pct:.1f}%)")
    
    # Receipt data availability
    cur.execute("SELECT COUNT(*), SUM(gross_amount) FROM receipts WHERE EXTRACT(YEAR FROM receipt_date) = %s", (year,))
    receipt_result = cur.fetchone()
    receipt_count = receipt_result[0] if receipt_result else 0  
    receipt_total = float(receipt_result[1]) if receipt_result and receipt_result[1] else 0
    
    print(f"🧾 Digital Receipts: {receipt_count} records, ${receipt_total:,.0f}")
    
    # Banking revenue estimate
    cur.execute("""
        SELECT COALESCE(SUM(credit_amount), 0) 
        FROM banking_transactions 
        WHERE EXTRACT(YEAR FROM transaction_date) = %s 
          AND credit_amount > 50
          AND description NOT ILIKE %s
          AND description NOT ILIKE %s
    """, (year, '%transfer%', '%loan%'))
    
    revenue_result = cur.fetchone()
    estimated_revenue = float(revenue_result[0]) if revenue_result and revenue_result[0] else 0
    
    print(f"📈 Estimated Revenue: ${estimated_revenue:,.0f} (from banking credits)")
    
    # Tax calculation estimate
    estimated_expenses = non_payroll_cash * 0.8  # Conservative: 80% of non-payroll cash = business expenses
    estimated_net_income = estimated_revenue - estimated_expenses - payroll_gross
    
    if estimated_net_income > 0:
        corporate_tax_rate = 0.13  # 2013-2015 Alberta small business rate
        estimated_tax = estimated_net_income * corporate_tax_rate
        print(f"🏛️ Estimated Tax: ${estimated_tax:,.0f} (13% on ${estimated_net_income:,.0f} net income)")
        
        # Potential tax savings from missing deductions
        if non_payroll_cash > payroll_net:
            potential_deductions = non_payroll_cash * 0.8  # 80% of non-payroll cash could be deductible
            tax_savings = potential_deductions * corporate_tax_rate
            print(f"💡 Potential Tax Savings: ${tax_savings:,.0f} (from ${potential_deductions:,.0f} missing expenses)")
    else:
        estimated_tax = 0
        tax_savings = 0
        print(f"📊 Estimated Loss: ${abs(estimated_net_income):,.0f}")
    
    # 2012 pattern comparison
    print(f"\n🎯 2012 Pattern Analysis:")
    if non_payroll_pct > 80:
        print(f"[OK] STRONG MATCH: {non_payroll_pct:.1f}% non-payroll cash (2012: 89.6%)")
        print(f"   Likely significant missing accountant receipts")
    elif non_payroll_pct > 50:
        print(f"📊 MODERATE MATCH: {non_payroll_pct:.1f}% non-payroll cash")  
        print(f"   Some missing business expenses likely")
    else:
        print(f"[FAIL] NO MATCH: {non_payroll_pct:.1f}% non-payroll cash")
        print(f"   Cash usage primarily for payroll")
    
    if receipt_count < 100:
        print(f"[OK] LIMITED RECEIPTS: {receipt_count} records (similar to 2012)")
        print(f"   Strong indicator of missing accountant data")
    
    cur.close()
    conn.close()
    
    return {
        'year': year,
        'payroll_net': payroll_net,
        'cash_total': cash_total, 
        'non_payroll_cash': non_payroll_cash,
        'non_payroll_percentage': non_payroll_pct,
        'receipt_count': receipt_count,
        'estimated_revenue': estimated_revenue,
        'estimated_tax': estimated_tax if 'estimated_tax' in locals() else 0,
        'potential_tax_savings': tax_savings if 'tax_savings' in locals() else 0
    }

def main():
    print("🚀 ROBUST MULTI-YEAR ANALYSIS: 2013-2015")
    print("=" * 45)
    print("Applying 2012 findings to identify missing receipt patterns")
    print("and quantify business expense recovery opportunities")
    
    years = [2013, 2014, 2015]
    results = {}
    
    for year in years:
        results[year] = analyze_year_simple(year)
    
    # Summary comparison
    print(f"\n📊 MULTI-YEAR SUMMARY")
    print("=" * 21)
    print(f"{'Year':<6} {'Cash':<10} {'Non-Pay%':<9} {'Receipts':<9} {'Tax Save':<10}")
    print("-" * 50)
    
    total_non_payroll = 0
    total_tax_savings = 0
    pattern_match_years = []
    
    for year in years:
        r = results[year]
        total_non_payroll += r['non_payroll_cash']
        total_tax_savings += r['potential_tax_savings']
        
        if r['non_payroll_percentage'] > 80:
            pattern_match_years.append(year)
            
        print(f"{year:<6} ${r['cash_total']:<9,.0f} {r['non_payroll_percentage']:<8.1f}% {r['receipt_count']:<8} ${r['potential_tax_savings']:<9,.0f}")
    
    print("-" * 50)
    print(f"{'TOTAL':<6} {'':<10} {'':<9} {'':<9} ${total_tax_savings:<9,.0f}")
    
    print(f"\n🎯 KEY FINDINGS")
    print("=" * 14)
    print(f"[OK] Years matching 2012 pattern: {len(pattern_match_years)}/3")
    if pattern_match_years:
        print(f"   Pattern match years: {', '.join(map(str, pattern_match_years))}")
    
    print(f"💰 Total non-payroll cash: ${total_non_payroll:,.0f}")
    print(f"💡 Estimated missing business expenses: ${total_non_payroll * 0.8:,.0f}")
    print(f"🏛️ Potential tax savings: ${total_tax_savings:,.0f}")
    
    # Business case
    print(f"\n💼 BUSINESS CASE FOR DATA RECOVERY")
    print("=" * 34)
    if total_tax_savings > 10000:
        print(f"🚀 STRONG CASE: ${total_tax_savings:,.0f} potential tax savings")
        print(f"   Justifies significant effort on accountant receipt recovery")
    elif total_tax_savings > 5000:
        print(f"📊 MODERATE CASE: ${total_tax_savings:,.0f} potential tax savings")
        print(f"   Worth focused effort on largest cash transactions")
    else:
        print(f"📋 LIMITED CASE: ${total_tax_savings:,.0f} potential tax savings")
    
    print(f"\n🎯 RECOMMENDED NEXT STEPS")
    print("=" * 25)
    print(f"1. Apply 2012 staging system to years: {', '.join(map(str, pattern_match_years))}")
    print(f"2. Focus on ${total_non_payroll:,.0f} in non-payroll cash transactions")
    print(f"3. Implement spot-check process (like Liquor Barn) for each year")
    print(f"4. Systematic cash-to-accountant receipt matching")
    print(f"5. Potential ROI: ${total_tax_savings:,.0f} tax savings + improved compliance")

if __name__ == '__main__':
    main()