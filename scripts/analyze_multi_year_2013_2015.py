#!/usr/bin/env python3
"""
Multi-Year Financial Analysis: 2013-2015
=========================================

Extend 2012 analysis procedures to check 2013-2015 for:
1. Tax calculation accuracy and position
2. Cash flow analysis and employee payroll separation  
3. Banking transaction documentation
4. Receipt completeness and missing accountant records
5. Business growth trends and data quality improvements

Based on successful 2012 findings:
- $23,710.94 net tax owing with $3,203.24 GST refund
- $727K cash activity (89.6% non-payroll business expenses)
- Missing accountant receipts pattern (Liquor Barn example)
- Need for systematic data recovery and staging processes

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
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
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

def analyze_year_financial_position(conn, year):
    """Comprehensive financial analysis for a specific year."""
    cur = conn.cursor()
    
    print(f"💰 FINANCIAL ANALYSIS - {year}")
    print("=" * 35)
    
    # 1. Revenue Analysis
    cur.execute("""
        SELECT 
            COUNT(*) as revenue_records,
            SUM(CASE WHEN gross_amount > 0 THEN gross_amount ELSE 0 END) as total_revenue,
            SUM(CASE WHEN gst_amount > 0 THEN gst_amount ELSE 0 END) as gst_collected,
            AVG(CASE WHEN gross_amount > 0 THEN gross_amount ELSE NULL END) as avg_revenue_per_record
        FROM receipts 
        WHERE EXTRACT(YEAR FROM receipt_date) = %s
          AND category IN ('revenue', 'charter_revenue', 'business_income')
    """, (year,))
    
    revenue_data = cur.fetchone()
    revenue_count, total_revenue, gst_collected, avg_revenue = revenue_data or (0, 0, 0, 0)
    
    # 2. Expense Analysis  
    cur.execute("""
        SELECT 
            COUNT(*) as expense_records,
            SUM(CASE WHEN gross_amount > 0 THEN gross_amount ELSE 0 END) as total_expenses,
            SUM(CASE WHEN gst_amount > 0 THEN gst_amount ELSE 0 END) as gst_paid,
            COUNT(DISTINCT vendor_name) as unique_vendors
        FROM receipts 
        WHERE EXTRACT(YEAR FROM receipt_date) = %s
          AND category NOT IN ('revenue', 'charter_revenue', 'business_income')
          AND gross_amount > 0
    """, (year,))
    
    expense_data = cur.fetchone()
    expense_count, total_expenses, gst_paid, unique_vendors = expense_data or (0, 0, 0, 0)
    
    # 3. Payroll Analysis
    cur.execute("""
        SELECT 
            COUNT(*) as payroll_records,
            SUM(gross_pay) as total_payroll,
            SUM(total_deductions) as total_deductions,
            SUM(net_pay) as total_net_pay,
            COUNT(DISTINCT driver_id) as unique_employees
        FROM driver_payroll 
        WHERE year = %s
    """, (year,))
    
    payroll_data = cur.fetchone()
    payroll_count, total_payroll, total_deductions, total_net_pay, unique_employees = payroll_data or (0, 0, 0, 0, 0)
    
    # 4. Banking Transaction Analysis
    cur.execute("""
        SELECT 
            COUNT(*) as banking_records,
            SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END) as total_deposits,
            SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END) as total_withdrawals,
            COUNT(CASE WHEN debit_amount > 0 AND description ILIKE '%cash%' THEN 1 END) as cash_withdrawals
        FROM banking_transactions 
        WHERE EXTRACT(YEAR FROM transaction_date) = %s
    """, (year,))
    
    banking_data = cur.fetchone()
    banking_count, total_deposits, total_withdrawals, cash_withdrawals = banking_data or (0, 0, 0, 0)
    
    # Handle None values and convert to Decimal for calculations
    total_revenue = Decimal(str(total_revenue or 0))
    total_expenses = Decimal(str(total_expenses or 0))
    total_payroll = Decimal(str(total_payroll or 0))
    gst_collected = Decimal(str(gst_collected or 0))
    gst_paid = Decimal(str(gst_paid or 0))
    
    # Calculate financial position
    net_income = total_revenue - total_expenses - total_payroll
    profit_margin = float((net_income / total_revenue) * 100) if total_revenue > 0 else 0
    
    # Tax calculation
    tax_rates = get_canadian_tax_rates(year)
    
    if net_income > 0 and net_income <= tax_rates['small_business_limit']:
        corporate_tax = net_income * Decimal(str(tax_rates['small_business_rate']))
    else:
        small_portion = min(net_income, Decimal(str(tax_rates['small_business_limit'])))
        large_portion = max(Decimal('0'), net_income - Decimal(str(tax_rates['small_business_limit'])))
        corporate_tax = (small_portion * Decimal(str(tax_rates['small_business_rate']))) + (large_portion * Decimal('0.27'))
    
    # GST/HST position
    gst_owing = gst_collected - gst_paid
    
    results = {
        'year': year,
        'revenue': {
            'records': revenue_count or 0,
            'total': total_revenue or 0,
            'gst_collected': gst_collected or 0,
            'average': avg_revenue or 0
        },
        'expenses': {
            'records': expense_count or 0,
            'total': total_expenses or 0,
            'gst_paid': gst_paid or 0,
            'vendors': unique_vendors or 0
        },
        'payroll': {
            'records': payroll_count or 0,
            'gross': total_payroll or 0,
            'deductions': total_deductions or 0,
            'net': total_net_pay or 0,
            'employees': unique_employees or 0
        },
        'banking': {
            'records': banking_count or 0,
            'deposits': total_deposits or 0,
            'withdrawals': total_withdrawals or 0,
            'cash_withdrawals': cash_withdrawals or 0
        },
        'financial_position': {
            'net_income': float(net_income),
            'profit_margin': profit_margin,
            'corporate_tax': float(corporate_tax),
            'gst_position': float(gst_owing),
            'tax_rates': tax_rates
        }
    }
    
    # Display results
    print(f"📊 Revenue: {revenue_count or 0:,} records, ${float(total_revenue):,.2f} total")
    print(f"💸 Expenses: {expense_count or 0:,} records, ${float(total_expenses):,.2f} total ({unique_vendors or 0} vendors)")
    print(f"👥 Payroll: {payroll_count or 0:,} records, ${float(total_payroll):,.2f} gross ({unique_employees or 0} employees)")
    print(f"🏦 Banking: {banking_count or 0:,} transactions, ${float(total_deposits or 0):,.2f} deposits, ${float(total_withdrawals or 0):,.2f} withdrawals")
    print()
    print(f"📈 Net Income: ${float(net_income):,.2f} ({profit_margin:.1f}% margin)")
    print(f"🏛️ Corporate Tax: ${float(corporate_tax):,.2f} ({tax_rates['small_business_rate']*100:.0f}% rate)")
    print(f"🧾 GST Position: ${float(gst_owing):,.2f} {'owing' if gst_owing > 0 else 'refund' if gst_owing < 0 else 'neutral'}")
    
    cur.close()
    return results

def analyze_cash_vs_payroll(conn, year):
    """Analyze cash withdrawals vs employee payroll for the year."""
    cur = conn.cursor()
    
    print(f"\n💵 CASH vs PAYROLL ANALYSIS - {year}")
    print("=" * 40)
    
    # Get cash withdrawals
    cur.execute("""
        SELECT 
            COUNT(*) as cash_transactions,
            SUM(debit_amount) as total_cash_withdrawals
        FROM banking_transactions 
        WHERE EXTRACT(YEAR FROM transaction_date) = %s
          AND debit_amount > 0 
          AND (description ILIKE '%cash%' 
               OR description ILIKE '%withdrawal%'
               OR description ILIKE '%atm%')
    """, (year,))
    
    cash_data = cur.fetchone()
    cash_count, total_cash = cash_data or (0, 0)
    
    # Get payroll total
    cur.execute("""
        SELECT 
            COUNT(*) as payroll_entries,
            SUM(gross_pay) as total_payroll_gross,
            SUM(net_pay) as total_payroll_net
        FROM driver_payroll 
        WHERE year = %s
    """, (year,))
    
    payroll_data = cur.fetchone()
    payroll_entries, payroll_gross, payroll_net = payroll_data or (0, 0, 0)
    
    # Calculate ratios
    cash_to_payroll_ratio = (total_cash or 0) / (payroll_net or 1) * 100 if payroll_net else 0
    non_payroll_cash = (total_cash or 0) - (payroll_net or 0)
    non_payroll_percentage = (non_payroll_cash / (total_cash or 1)) * 100 if total_cash else 0
    
    print(f"💰 Cash Withdrawals: {cash_count or 0} transactions, ${total_cash or 0:,.2f}")
    print(f"👥 Payroll Net: {payroll_entries or 0} entries, ${payroll_net or 0:,.2f}")
    print(f"📊 Cash/Payroll Ratio: {cash_to_payroll_ratio:.1f}%")
    print(f"🏢 Non-Payroll Cash: ${non_payroll_cash:,.2f} ({non_payroll_percentage:.1f}%)")
    
    if non_payroll_percentage > 80:
        print(f"[WARN]  Similar to 2012: Majority of cash represents business expenses")
    elif non_payroll_percentage > 50:
        print(f"📈 Moderate business cash usage beyond payroll")
    else:
        print(f"[OK] Cash usage primarily for payroll")
    
    cur.close()
    
    return {
        'cash_withdrawals': total_cash or 0,
        'payroll_net': payroll_net or 0,
        'non_payroll_cash': non_payroll_cash,
        'non_payroll_percentage': non_payroll_percentage
    }

def check_missing_receipts_pattern(conn, year):
    """Check for missing receipt patterns like we found with Liquor Barn."""
    cur = conn.cursor()
    
    print(f"\n🧾 RECEIPT COMPLETENESS CHECK - {year}")
    print("=" * 42)
    
    # Get receipt statistics
    cur.execute("""
        SELECT 
            COUNT(*) as total_receipts,
            COUNT(DISTINCT vendor_name) as unique_vendors,
            SUM(gross_amount) as total_receipt_amount,
            AVG(gross_amount) as avg_receipt_amount,
            COUNT(*) FILTER (WHERE source_system = 'manual_entry') as manual_entries,
            COUNT(*) FILTER (WHERE source_system ILIKE '%import%') as imported_entries
        FROM receipts 
        WHERE EXTRACT(YEAR FROM receipt_date) = %s
    """, (year,))
    
    receipt_stats = cur.fetchone()
    total_receipts, unique_vendors, total_amount, avg_amount, manual_entries, imported_entries = receipt_stats or (0, 0, 0, 0, 0, 0)
    
    # Check for common business expense vendors that might be missing
    common_vendors = ['liquor', 'gas', 'fuel', 'office', 'insurance', 'bank', 'maintenance', 'repair']
    
    print(f"📋 Total Receipts: {total_receipts or 0:,}")
    print(f"🏪 Unique Vendors: {unique_vendors or 0}")
    print(f"💰 Total Amount: ${total_amount or 0:,.2f}")
    print(f"📊 Average Receipt: ${avg_amount or 0:.2f}")
    print(f"✍️  Manual Entries: {manual_entries or 0} ({((manual_entries or 0)/(total_receipts or 1)*100):.1f}%)")
    print(f"📥 Imported Entries: {imported_entries or 0} ({((imported_entries or 0)/(total_receipts or 1)*100):.1f}%)")
    
    # Check for vendor coverage gaps
    print(f"\n🔍 Common Vendor Coverage:")
    vendor_gaps = []
    
    for vendor_type in common_vendors:
        cur.execute("""
            SELECT COUNT(*), SUM(gross_amount)
            FROM receipts 
            WHERE EXTRACT(YEAR FROM receipt_date) = %s
              AND (vendor_name ILIKE %s OR description ILIKE %s)
        """, (year, f'%{vendor_type}%', f'%{vendor_type}%'))
        
        count, amount = cur.fetchone()
        if count == 0:
            vendor_gaps.append(vendor_type)
            print(f"[FAIL] {vendor_type.title()}: No receipts found")
        else:
            print(f"[OK] {vendor_type.title()}: {count} receipts, ${amount or 0:.2f}")
    
    if vendor_gaps:
        print(f"\n[WARN]  Missing vendor types: {', '.join(vendor_gaps)}")
        print(f"💡 These may indicate missing receipt data like we found in 2012")
    
    cur.close()
    
    return {
        'total_receipts': total_receipts or 0,
        'unique_vendors': unique_vendors or 0,
        'manual_entries': manual_entries or 0,
        'imported_entries': imported_entries or 0,
        'vendor_gaps': vendor_gaps
    }

def analyze_banking_coverage(conn, year):
    """Analyze banking transaction documentation coverage."""
    cur = conn.cursor()
    
    print(f"\n🏦 BANKING DOCUMENTATION - {year}")
    print("=" * 35)
    
    # Banking transaction summary
    cur.execute("""
        SELECT 
            COUNT(*) as total_transactions,
            SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END) as total_debits,
            SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END) as total_credits,
            COUNT(CASE WHEN category IS NOT NULL THEN 1 END) as categorized_transactions,
            COUNT(CASE WHEN vendor_name IS NOT NULL THEN 1 END) as vendor_identified
        FROM banking_transactions 
        WHERE EXTRACT(YEAR FROM transaction_date) = %s
    """, (year,))
    
    banking_stats = cur.fetchone()
    total_txns, total_debits, total_credits, categorized, vendor_identified = banking_stats or (0, 0, 0, 0, 0)
    
    categorization_rate = (categorized / total_txns * 100) if total_txns else 0
    vendor_rate = (vendor_identified / total_txns * 100) if total_txns else 0
    
    print(f"📊 Total Transactions: {total_txns:,}")
    print(f"📤 Total Debits: ${total_debits:,.2f}")
    print(f"📥 Total Credits: ${total_credits:,.2f}")
    print(f"🏷️  Categorized: {categorized:,} ({categorization_rate:.1f}%)")
    print(f"🏪 Vendor ID'd: {vendor_identified:,} ({vendor_rate:.1f}%)")
    
    # Compare to 2012 success rate
    if year > 2012:
        print(f"\n📈 Documentation Quality:")
        if categorization_rate > 90:
            print(f"[OK] Excellent categorization ({categorization_rate:.1f}%)")
        elif categorization_rate > 70:
            print(f"[OK] Good categorization ({categorization_rate:.1f}%)")
        else:
            print(f"[WARN]  Low categorization ({categorization_rate:.1f}%) - improvement needed")
    
    cur.close()
    
    return {
        'total_transactions': total_txns,
        'categorization_rate': categorization_rate,
        'vendor_identification_rate': vendor_rate
    }

def multi_year_comprehensive_analysis(years):
    """Run comprehensive analysis across multiple years."""
    
    print("🚀 MULTI-YEAR FINANCIAL ANALYSIS: 2013-2015")
    print("=" * 50)
    print("Applying 2012 analysis procedures to identify patterns,")
    print("missing data, and optimization opportunities across years.")
    print()
    
    conn = get_db_connection()
    
    all_results = {}
    
    try:
        for year in years:
            print(f"\n" + "="*60)
            print(f"📅 ANALYZING YEAR {year}")
            print("="*60)
            
            # Core financial analysis
            financial_results = analyze_year_financial_position(conn, year)
            
            # Cash vs payroll analysis
            cash_results = analyze_cash_vs_payroll(conn, year)
            
            # Receipt completeness check
            receipt_results = check_missing_receipts_pattern(conn, year)
            
            # Banking documentation analysis
            banking_results = analyze_banking_coverage(conn, year)
            
            # Compile results
            all_results[year] = {
                'financial': financial_results,
                'cash_analysis': cash_results,
                'receipts': receipt_results,
                'banking': banking_results
            }
        
        # Multi-year comparison
        print(f"\n" + "="*60)
        print(f"📊 MULTI-YEAR COMPARISON & TRENDS")
        print("="*60)
        
        print(f"{'Year':<6} {'Revenue':<12} {'Net Income':<12} {'Tax':<10} {'Margin':<8} {'Cash/Pay':<10}")
        print("-" * 70)
        
        for year in years:
            results = all_results[year]
            revenue = results['financial']['revenue']['total']
            net_income = results['financial']['financial_position']['net_income']
            tax = results['financial']['financial_position']['corporate_tax']
            margin = results['financial']['financial_position']['profit_margin']
            cash_ratio = results['cash_analysis']['non_payroll_percentage']
            
            print(f"{year:<6} ${revenue:<11,.0f} ${net_income:<11,.0f} ${tax:<9,.0f} {margin:<7.1f}% {cash_ratio:<9.1f}%")
        
        # Identify patterns and issues
        print(f"\n🔍 KEY FINDINGS & PATTERNS")
        print("=" * 26)
        
        # Tax trend
        tax_2013 = all_results[2013]['financial']['financial_position']['corporate_tax']
        tax_2015 = all_results[2015]['financial']['financial_position']['corporate_tax']
        
        print(f"💰 Tax Burden: {2013} ${tax_2013:,.0f} → {2015} ${tax_2015:,.0f}")
        
        # Revenue growth
        rev_2013 = all_results[2013]['financial']['revenue']['total']
        rev_2015 = all_results[2015]['financial']['revenue']['total']
        growth_rate = ((rev_2015 / rev_2013) - 1) * 100 if rev_2013 else 0
        
        print(f"📈 Revenue Growth: {growth_rate:+.1f}% over 3 years")
        
        # Data quality trends
        receipt_gaps_by_year = [(year, len(all_results[year]['receipts']['vendor_gaps'])) for year in years]
        banking_quality_by_year = [(year, all_results[year]['banking']['categorization_rate']) for year in years]
        
        print(f"\n📋 Data Quality Trends:")
        for year, gaps in receipt_gaps_by_year:
            categorization = [rate for y, rate in banking_quality_by_year if y == year][0]
            print(f"  {year}: {gaps} vendor gaps, {categorization:.1f}% banking categorization")
        
        # Missing data estimate
        total_non_payroll_cash = sum(all_results[year]['cash_analysis']['non_payroll_cash'] for year in years)
        print(f"\n💡 BUSINESS OPPORTUNITY")
        print("=" * 22)
        print(f"Total Non-Payroll Cash (2013-2015): ${total_non_payroll_cash:,.2f}")
        print(f"Potential Additional Business Deductions Available")
        print(f"Estimated Tax Benefit: ${total_non_payroll_cash * 0.13:,.2f} (13% corporate rate)")
        
        # Recommendations
        print(f"\n🎯 RECOMMENDED ACTIONS")
        print("=" * 21)
        
        high_cash_years = [year for year in years if all_results[year]['cash_analysis']['non_payroll_percentage'] > 80]
        if high_cash_years:
            print(f"1. Years {', '.join(map(str, high_cash_years))}: Investigate high non-payroll cash like 2012")
        
        low_quality_years = [year for year in years if all_results[year]['banking']['categorization_rate'] < 80]
        if low_quality_years:
            print(f"2. Years {', '.join(map(str, low_quality_years))}: Improve banking transaction categorization")
        
        gap_years = [year for year in years if len(all_results[year]['receipts']['vendor_gaps']) > 3]
        if gap_years:
            print(f"3. Years {', '.join(map(str, gap_years))}: Check for missing receipt patterns")
        
        print(f"4. Consider staging system for manual receipt entry across all years")
        print(f"5. Implement systematic accountant receipt reconciliation process")
        
        # Save results
        with open(f'multi_year_analysis_2013_2015.json', 'w') as f:
            json.dump(all_results, f, indent=2, default=str)
        
        print(f"\n[OK] Analysis complete - results saved to multi_year_analysis_2013_2015.json")
        
    except Exception as e:
        print(f"[FAIL] Error during analysis: {e}")
        return 1
    
    finally:
        conn.close()
    
    return 0

def main():
    years = [2013, 2014, 2015]
    return multi_year_comprehensive_analysis(years)

if __name__ == '__main__':
    sys.exit(main())