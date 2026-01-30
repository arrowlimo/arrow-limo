#!/usr/bin/env python3
"""
Targeted Multi-Year Analysis: 2013-2015
=======================================

Based on data availability check:
- 2013: 55 receipts, 1,585 payroll, 1,069 banking
- 2014: 1 receipt, 1,683 payroll, 177 banking  
- 2015: 0 receipts, 1,496 payroll, 305 banking

Focus on payroll and banking analysis since receipt data is limited.
This mirrors the 2012 pattern where most business expenses were missing 
from digital records but existed in accountant cash records.

Author: AI Agent
Date: October 2025
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from decimal import Decimal
from datetime import datetime
import json

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def get_canadian_tax_rates(year):
    """Get Canadian corporate tax rates by year."""
    rates = {
        2012: {'small_business_rate': 0.14, 'gst_rate': 0.05, 'small_business_limit': 400000},
        2013: {'small_business_rate': 0.13, 'gst_rate': 0.05, 'small_business_limit': 400000},
        2014: {'small_business_rate': 0.13, 'gst_rate': 0.05, 'small_business_limit': 400000},
        2015: {'small_business_rate': 0.13, 'gst_rate': 0.05, 'small_business_limit': 400000}
    }
    return rates.get(year, rates[2015])

def analyze_payroll_and_cash(conn, year):
    """Focus on payroll and cash analysis for years with limited receipt data."""
    cur = conn.cursor()
    
    print(f"💼 PAYROLL & CASH ANALYSIS - {year}")
    print("=" * 38)
    
    # Payroll analysis
    cur.execute("""
        SELECT 
            COUNT(*) as entries,
            SUM(gross_pay) as total_gross,
            SUM(total_deductions) as total_deductions, 
            SUM(net_pay) as total_net,
            COUNT(DISTINCT driver_id) as unique_drivers,
            AVG(gross_pay) as avg_gross_per_entry,
            MIN(pay_date) as earliest_pay,
            MAX(pay_date) as latest_pay
        FROM driver_payroll 
        WHERE year = %s
    """, (year,))
    
    payroll = cur.fetchone()
    if payroll and payroll[0] > 0:
        entries, gross, deductions, net, drivers, avg_gross, earliest, latest = payroll
        
        print(f"👥 Payroll Summary:")
        print(f"  Entries: {entries:,}")
        print(f"  Unique Drivers: {drivers}")  
        print(f"  Total Gross: ${gross:,.2f}")
        print(f"  Total Deductions: ${deductions:,.2f}")
        print(f"  Total Net: ${net:,.2f}")
        print(f"  Average per Entry: ${avg_gross:.2f}")
        print(f"  Date Range: {earliest} to {latest}")
    else:
        print(f"[FAIL] No payroll data for {year}")
        gross, deductions, net, drivers = 0, 0, 0, 0
    
    # Banking analysis
    cur.execute("""
        SELECT 
            COUNT(*) as total_transactions,
            SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END) as total_debits,
            SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END) as total_credits,
            COUNT(CASE WHEN debit_amount > 0 AND (description ILIKE '%cash%' OR description ILIKE '%withdrawal%') THEN 1 END) as cash_withdrawals,
            SUM(CASE WHEN debit_amount > 0 AND (description ILIKE '%cash%' OR description ILIKE '%withdrawal%') THEN debit_amount ELSE 0 END) as cash_amount
        FROM banking_transactions 
        WHERE EXTRACT(YEAR FROM transaction_date) = %s
    """, (year,))
    
    banking = cur.fetchone()
    if banking and len(banking) >= 5:
        total_txns, debits, credits, cash_count, cash_amount = banking
        
        print(f"\n🏦 Banking Summary:")
        print(f"  Total Transactions: {total_txns:,}")
        print(f"  Total Debits: ${debits or 0:,.2f}")
        print(f"  Total Credits: ${credits or 0:,.2f}")
        print(f"  Cash Withdrawals: {cash_count} transactions")
        print(f"  Cash Amount: ${cash_amount or 0:,.2f}")
        
        # Cash vs Payroll analysis (like 2012)
        if net and cash_amount:
            cash_to_payroll = (cash_amount / net) * 100
            non_payroll_cash = cash_amount - net
            non_payroll_percentage = (non_payroll_cash / cash_amount) * 100 if cash_amount > 0 else 0
            
            print(f"\n📊 Cash vs Payroll Analysis:")
            print(f"  Cash/Payroll Ratio: {cash_to_payroll:.1f}%")
            print(f"  Non-Payroll Cash: ${non_payroll_cash:,.2f}")
            print(f"  Non-Payroll %: {non_payroll_percentage:.1f}%")
            
            if non_payroll_percentage > 80:
                print(f"  🎯 Similar to 2012: Majority cash = business expenses")
            elif non_payroll_percentage > 50:
                print(f"  📈 Significant business cash beyond payroll")
            else:
                print(f"  [OK] Cash usage primarily for payroll")
        else:
            non_payroll_cash, non_payroll_percentage = 0, 0
    else:
        total_txns, debits, credits, cash_count, cash_amount = 0, 0, 0, 0, 0
        non_payroll_cash, non_payroll_percentage = 0, 0
    
    # Limited receipt analysis
    cur.execute("""
        SELECT 
            COUNT(*) as receipt_count,
            SUM(gross_amount) as total_receipts,
            COUNT(DISTINCT vendor_name) as unique_vendors
        FROM receipts 
        WHERE EXTRACT(YEAR FROM receipt_date) = %s
    """, (year,))
    
    receipts = cur.fetchone()
    if receipts and len(receipts) >= 3:
        receipt_count, receipt_total, receipt_vendors = receipts
    else:
        receipt_count, receipt_total, receipt_vendors = 0, 0, 0
    
    print(f"\n🧾 Receipt Summary:")
    print(f"  Digital Receipts: {receipt_count or 0}")
    print(f"  Total Amount: ${receipt_total or 0:.2f}")
    print(f"  Unique Vendors: {receipt_vendors or 0}")
    
    if (receipt_count or 0) < 100:
        print(f"  [WARN] Very limited receipt data - similar to 2012 pattern")
        print(f"  💡 Likely significant missing accountant receipts")
    
    cur.close()
    
    # Ensure all variables are defined
    entries = entries if 'entries' in locals() else 0
    gross = gross if 'gross' in locals() and gross else 0
    net = net if 'net' in locals() and net else 0
    drivers = drivers if 'drivers' in locals() else 0
    total_txns = total_txns if 'total_txns' in locals() else 0
    cash_amount = cash_amount if 'cash_amount' in locals() else 0
    debits = debits if 'debits' in locals() else 0
    credits = credits if 'credits' in locals() else 0
    non_payroll_cash = non_payroll_cash if 'non_payroll_cash' in locals() else 0
    non_payroll_percentage = non_payroll_percentage if 'non_payroll_percentage' in locals() else 0
    
    return {
        'payroll': {
            'entries': entries,
            'gross': float(gross),
            'net': float(net),
            'drivers': drivers
        },
        'banking': {
            'transactions': total_txns,
            'cash_amount': float(cash_amount),
            'debits': float(debits),
            'credits': float(credits)
        },
        'cash_analysis': {
            'non_payroll_cash': float(non_payroll_cash),
            'non_payroll_percentage': float(non_payroll_percentage)
        },
        'receipts': {
            'count': receipt_count or 0,
            'total': float(receipt_total) if receipt_total else 0,
            'vendors': receipt_vendors or 0
        }
    }

def estimate_revenue_from_banking(conn, year):
    """Estimate revenue from banking credits since receipt data is limited."""
    cur = conn.cursor()
    
    print(f"\n💰 REVENUE ESTIMATION FROM BANKING - {year}")
    print("=" * 45)
    
    # Analyze credit transactions for revenue indicators
    cur.execute("""
        SELECT 
            SUM(credit_amount) as total_credits,
            COUNT(*) as credit_count,
            AVG(credit_amount) as avg_credit,
            COUNT(CASE WHEN description ILIKE '%deposit%' THEN 1 END) as deposits,
            COUNT(CASE WHEN description ILIKE '%transfer%' THEN 1 END) as transfers,
            COUNT(CASE WHEN description ILIKE '%payment%' THEN 1 END) as payments
        FROM banking_transactions 
        WHERE EXTRACT(YEAR FROM transaction_date) = %s
          AND credit_amount > 0
    """, (year,))
    
    credits = cur.fetchone()
    if credits and len(credits) >= 6:
        total, count, average, deposits, transfers, payments = credits
    else:
        total, count, average, deposits, transfers, payments = 0, 0, 0, 0, 0, 0
        
        print(f"📈 Banking Credits Analysis:")
        print(f"  Total Credits: ${total or 0:,.2f}")
        print(f"  Credit Count: {count}")
        print(f"  Average Credit: ${average or 0:.2f}")
        print(f"  Deposits: {deposits}")
        print(f"  Transfers: {transfers}")
        print(f"  Payments: {payments}")
        
        # Estimate business revenue (excluding obvious non-revenue items)
        cur.execute("""
            SELECT SUM(credit_amount)
            FROM banking_transactions 
            WHERE EXTRACT(YEAR FROM transaction_date) = %s
              AND credit_amount > 0
              AND description NOT ILIKE '%transfer%'
              AND description NOT ILIKE '%loan%'
              AND description NOT ILIKE '%refund%'
              AND credit_amount > 50  -- Exclude small miscellaneous credits
        """, (year,))
        
        estimated_revenue = cur.fetchone()[0] or 0
        
        print(f"\n💡 Estimated Business Revenue: ${estimated_revenue:,.2f}")
        print(f"   (Excludes transfers, loans, refunds, credits <$50)")
        
        # Compare to payroll for reasonableness
        cur.execute("""SELECT SUM(gross_pay) FROM driver_payroll WHERE year = %s""", (year,))
        payroll_total = cur.fetchone()[0] or 0
        
        if payroll_total > 0:
            revenue_to_payroll = (estimated_revenue / payroll_total) * 100
            print(f"   Revenue/Payroll Ratio: {revenue_to_payroll:.1f}%")
            
            if revenue_to_payroll > 200:
                print(f"   [OK] Reasonable ratio - profitable business")
            elif revenue_to_payroll > 100:
                print(f"   📊 Moderate ratio - check expense coverage")
            else:
                print(f"   [WARN] Low ratio - may indicate missing revenue data")
    
    cur.close()
    return estimated_revenue or 0

def calculate_tax_estimate(revenue, payroll_gross, non_payroll_cash, year):
    """Calculate rough tax estimate with limited expense data."""
    
    print(f"\n🧮 TAX ESTIMATION - {year}")
    print("=" * 25)
    
    tax_rates = get_canadian_tax_rates(year)
    
    # Conservative expense estimate
    # Use non-payroll cash as proxy for business expenses (like 2012 finding)
    estimated_expenses = non_payroll_cash * 0.8  # Conservative: 80% of cash = deductible expenses
    
    # Calculate estimated taxable income
    estimated_net_income = revenue - estimated_expenses - payroll_gross
    
    print(f"📊 Tax Calculation Estimate:")
    print(f"  Estimated Revenue: ${revenue:,.2f}")
    print(f"  Estimated Expenses: ${estimated_expenses:,.2f} (from {non_payroll_cash:,.2f} cash)")
    print(f"  Payroll Gross: ${payroll_gross:,.2f}")
    print(f"  Estimated Net Income: ${estimated_net_income:,.2f}")
    
    if estimated_net_income > 0:
        if estimated_net_income <= tax_rates['small_business_limit']:
            estimated_tax = estimated_net_income * tax_rates['small_business_rate']
            print(f"  Corporate Tax ({tax_rates['small_business_rate']*100:.0f}%): ${estimated_tax:,.2f}")
        else:
            small_portion = tax_rates['small_business_limit'] * tax_rates['small_business_rate']
            large_portion = (estimated_net_income - tax_rates['small_business_limit']) * 0.27
            estimated_tax = small_portion + large_portion
            print(f"  Corporate Tax (mixed rate): ${estimated_tax:,.2f}")
        
        profit_margin = (estimated_net_income / revenue) * 100 if revenue > 0 else 0
        print(f"  Estimated Profit Margin: {profit_margin:.1f}%")
    else:
        estimated_tax = 0
        print(f"  Estimated Loss: ${abs(estimated_net_income):,.2f}")
        print(f"  No Corporate Tax Owing")
    
    # Missing data impact
    print(f"\n💡 Data Completeness Impact:")
    if estimated_expenses < non_payroll_cash * 0.5:
        potential_additional_deductions = non_payroll_cash * 0.7 - estimated_expenses
        tax_savings = potential_additional_deductions * tax_rates['small_business_rate']
        print(f"  Potential Additional Deductions: ${potential_additional_deductions:,.2f}")
        print(f"  Potential Tax Savings: ${tax_savings:,.2f}")
    
    return {
        'estimated_revenue': revenue,
        'estimated_expenses': estimated_expenses,
        'estimated_net_income': estimated_net_income,
        'estimated_tax': estimated_tax,
        'tax_rate_used': tax_rates['small_business_rate']
    }

def comprehensive_year_analysis(conn, year):
    """Complete analysis for a single year."""
    print(f"\n" + "="*60)
    print(f"📅 COMPREHENSIVE ANALYSIS - {year}")
    print("="*60)
    
    # Core payroll and cash analysis
    payroll_cash_results = analyze_payroll_and_cash(conn, year)
    
    # Revenue estimation from banking
    estimated_revenue = estimate_revenue_from_banking(conn, year)
    
    # Tax calculation
    tax_results = calculate_tax_estimate(
        estimated_revenue,
        payroll_cash_results['payroll']['gross'],
        payroll_cash_results['cash_analysis']['non_payroll_cash'],
        year
    )
    
    # Data quality assessment
    print(f"\n📋 DATA QUALITY ASSESSMENT - {year}")
    print("=" * 40)
    
    receipt_count = payroll_cash_results['receipts']['count']
    payroll_entries = payroll_cash_results['payroll']['entries'] 
    banking_txns = payroll_cash_results['banking']['transactions']
    
    print(f"📊 Data Availability:")
    print(f"  Receipts: {receipt_count} ({'Limited' if receipt_count < 100 else 'Adequate'})")
    print(f"  Payroll: {payroll_entries} ({'Good' if payroll_entries > 1000 else 'Moderate'})")  
    print(f"  Banking: {banking_txns} ({'Good' if banking_txns > 500 else 'Limited'})")
    
    # Compare to 2012 pattern
    non_payroll_pct = payroll_cash_results['cash_analysis']['non_payroll_percentage']
    if non_payroll_pct > 80:
        print(f"🎯 2012 Pattern Match: {non_payroll_pct:.1f}% non-payroll cash")
        print(f"   Likely significant missing accountant receipts")
    
    return {
        'year': year,
        'payroll_cash': payroll_cash_results,
        'revenue_estimate': estimated_revenue,
        'tax_estimate': tax_results,
        'data_quality': {
            'receipts': receipt_count,
            'payroll': payroll_entries,
            'banking': banking_txns,
            'pattern_match_2012': non_payroll_pct > 80
        }
    }

def multi_year_summary(all_results):
    """Generate multi-year comparison and findings."""
    
    print(f"\n" + "="*60)
    print(f"📊 MULTI-YEAR SUMMARY & COMPARISON")
    print("="*60)
    
    print(f"{'Year':<6} {'Est.Revenue':<12} {'Payroll':<10} {'Non-Pay Cash':<12} {'Est.Tax':<10} {'Data'}")
    print("-" * 70)
    
    total_non_payroll_cash = 0
    total_estimated_tax = 0
    
    for year, results in all_results.items():
        revenue = results['revenue_estimate']
        payroll = results['payroll_cash']['payroll']['gross']
        non_payroll = results['payroll_cash']['cash_analysis']['non_payroll_cash']
        tax = results['tax_estimate']['estimated_tax']
        receipts = results['data_quality']['receipts']
        
        total_non_payroll_cash += non_payroll
        total_estimated_tax += tax
        
        data_quality = "Limited" if receipts < 100 else "Good"
        
        print(f"{year:<6} ${revenue:<11,.0f} ${payroll:<9,.0f} ${non_payroll:<11,.0f} ${tax:<9,.0f} {data_quality}")
    
    print("-" * 70)
    print(f"{'TOTAL':<6} {'':<12} {'':<10} ${total_non_payroll_cash:<11,.0f} ${total_estimated_tax:<9,.0f}")
    
    print(f"\n🔍 KEY FINDINGS (2013-2015)")
    print("=" * 28)
    
    # Pattern analysis
    pattern_years = [year for year, results in all_results.items() 
                    if results['data_quality']['pattern_match_2012']]
    
    if pattern_years:
        print(f"🎯 Years matching 2012 pattern: {', '.join(map(str, pattern_years))}")
        print(f"   High non-payroll cash suggests missing receipt data")
    
    # Revenue trend
    revenues = [results['revenue_estimate'] for results in all_results.values()]
    if len(revenues) >= 2:
        growth = ((revenues[-1] / revenues[0]) - 1) * 100 if revenues[0] > 0 else 0
        print(f"📈 Revenue trend: {growth:+.1f}% over period")
    
    # Tax burden  
    print(f"💰 Total estimated tax (2013-2015): ${total_estimated_tax:,.2f}")
    
    # Business opportunity
    print(f"\n💡 BUSINESS OPPORTUNITY")
    print("=" * 22)
    print(f"Total Non-Payroll Cash: ${total_non_payroll_cash:,.2f}")
    print(f"Estimated Missing Business Expenses: ${total_non_payroll_cash * 0.8:,.2f}")
    print(f"Potential Additional Tax Deductions: ${total_non_payroll_cash * 0.8:,.2f}")
    print(f"Estimated Tax Savings (13% rate): ${total_non_payroll_cash * 0.8 * 0.13:,.2f}")
    
    print(f"\n🎯 RECOMMENDED ACTIONS")
    print("=" * 21)
    print(f"1. Apply 2012 accountant receipt recovery process to 2013-2015")
    print(f"2. Investigate ${total_non_payroll_cash:,.2f} in non-payroll cash payments")
    print(f"3. Create staging system for missing receipts (like 2012 Liquor Barn)")
    print(f"4. Systematic cash-to-receipt matching across all years")
    print(f"5. Potential tax benefit of ${total_non_payroll_cash * 0.8 * 0.13:,.2f} justifies effort")

def main():
    print("🚀 TARGETED MULTI-YEAR ANALYSIS: 2013-2015")
    print("=" * 50)
    print("Based on data availability, focusing on payroll and banking analysis")
    print("to identify patterns similar to 2012 missing receipt situation.")
    print()
    
    conn = get_db_connection()
    years = [2013, 2014, 2015]
    all_results = {}
    
    try:
        for year in years:
            all_results[year] = comprehensive_year_analysis(conn, year)
        
        # Multi-year summary
        multi_year_summary(all_results)
        
        # Save results
        with open('targeted_analysis_2013_2015.json', 'w') as f:
            json.dump(all_results, f, indent=2, default=str)
        
        print(f"\n[OK] Analysis complete - saved to targeted_analysis_2013_2015.json")
        
    except Exception as e:
        print(f"[FAIL] Error during analysis: {e}")
        return 1
    
    finally:
        conn.close()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())