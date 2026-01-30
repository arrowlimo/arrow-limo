#!/usr/bin/env python3
"""
Generate T2 Corporate Tax Return Summary for Arrow Limousine.

Provides:
- Income statement (revenue/expenses)
- Expense categories for tax deductions
- Receipts summary
- Tax-deductible expenses analysis
"""
import os
import psycopg2
from datetime import datetime
from decimal import Decimal

# Use localhost explicitly (not .env which may point to Neon remote)
DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REDACTED***"

def main():
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    year = input("Enter tax year (e.g., 2013, 2014): ").strip()
    if not year.isdigit():
        print("Invalid year")
        return
    year = int(year)
    
    report_file = f"reports/T2_TAX_SUMMARY_{year}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("ARROW LIMOUSINE & SEDAN SERVICES LTD.\n")
        f.write(f"T2 CORPORATE TAX RETURN SUMMARY - {year}\n")
        f.write("=" * 80 + "\n")
        f.write(f"Report Date: {datetime.now().strftime('%B %d, %Y')}\n\n")
        
        # REVENUE
        f.write("=" * 80 + "\n")
        f.write("REVENUE SUMMARY\n")
        f.write("=" * 80 + "\n\n")
        
        cur.execute("""
            SELECT 
                COUNT(*) as charter_count,
                SUM(total_amount_due) as total_revenue,
                SUM(driver_gratuity) as total_gratuity,
                SUM(total_amount_due - COALESCE(driver_gratuity, 0)) as net_revenue
            FROM charters
            WHERE EXTRACT(YEAR FROM charter_date) = %s
            AND total_amount_due IS NOT NULL
        """, (year,))
        
        revenue = cur.fetchone()
        f.write(f"Charters completed: {revenue[0]:,}\n")
        f.write(f"Gross revenue (incl. gratuity): ${revenue[1] or 0:,.2f}\n")
        f.write(f"Less: Direct tips to drivers: ${revenue[2] or 0:,.2f}\n")
        f.write(f"NET TAXABLE REVENUE: ${revenue[3] or 0:,.2f}\n\n")
        
        # Charter status breakdown
        cur.execute("""
            SELECT 
                status,
                COUNT(*) as count,
                SUM(total_amount_due) as total
            FROM charters
            WHERE EXTRACT(YEAR FROM charter_date) = %s
            AND total_amount_due IS NOT NULL
            GROUP BY status
            ORDER BY total DESC
        """, (year,))
        
        f.write("Charter Status Breakdown:\n")
        for status_row in cur.fetchall():
            status = status_row[0] or 'Unknown'
            f.write(f"  {status}: {status_row[1]:,} charters, ${status_row[2]:,.2f}\n")
        f.write("\n")
        
        # EXPENSES
        f.write("=" * 80 + "\n")
        f.write("BUSINESS EXPENSES (Tax Deductible)\n")
        f.write("=" * 80 + "\n\n")
        
        cur.execute("""
            SELECT 
                COALESCE(vendor_name, 'Unknown') as vendor_name,
                COUNT(*) as receipt_count,
                SUM(gross_amount) as total_amount
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = %s
            AND gross_amount IS NOT NULL
            AND gross_amount > 0
            GROUP BY vendor_name
            ORDER BY total_amount DESC
            LIMIT 30
        """, (year,))
        
        f.write(f"{'Vendor/Expense Category':<40} {'Receipts':<10} {'Amount':<15}\n")
        f.write("-" * 65 + "\n")
        
        total_expenses = Decimal(0)
        for row in cur.fetchall():
            f.write(f"{(row[0] or 'Unknown')[:39]:<40} {row[1]:>9,} ${row[2]:>14,.2f}\n")
            total_expenses += row[2]
        
        f.write("-" * 65 + "\n")
        f.write(f"{'TOTAL EXPENSES':<40} {'':<10} ${total_expenses:>14,.2f}\n\n")
        
        # NET INCOME
        f.write("=" * 80 + "\n")
        f.write("NET INCOME CALCULATION\n")
        f.write("=" * 80 + "\n\n")
        
        net_revenue = revenue[3] or Decimal(0)
        net_income = net_revenue - total_expenses
        
        f.write(f"Net Revenue: ${net_revenue:,.2f}\n")
        f.write(f"Less: Total Expenses: ${total_expenses:,.2f}\n")
        f.write(f"NET INCOME (LOSS): ${net_income:,.2f}\n\n")
        
        # PAYMENT RECONCILIATION
        f.write("=" * 80 + "\n")
        f.write("PAYMENT RECONCILIATION\n")
        f.write("=" * 80 + "\n\n")
        
        cur.execute("""
            SELECT 
                COUNT(*) as payment_count,
                SUM(amount) as total_received
            FROM payments
            WHERE EXTRACT(YEAR FROM payment_date) = %s
            AND amount IS NOT NULL
        """, (year,))
        
        payment_data = cur.fetchone()
        payments_received = payment_data[1] or Decimal(0)
        
        f.write(f"Total payments received: ${payments_received:,.2f}\n")
        f.write(f"Charter revenue recorded: ${revenue[1] or 0:,.2f}\n")
        variance = payments_received - (revenue[1] or 0)
        f.write(f"Variance: ${variance:,.2f}\n\n")
        
        if abs(variance) > 100:
            f.write("⚠️  Note: Variance may include:\n")
            f.write("   - Deposits for future charters\n")
            f.write("   - Refunds issued\n")
            f.write("   - Payments spanning multiple years\n\n")
        
        # MISSING RECEIPTS IMPACT
        f.write("=" * 80 + "\n")
        f.write("MISSING RECEIPTS IMPACT ANALYSIS\n")
        f.write("=" * 80 + "\n\n")
        
        cur.execute("""
            SELECT COUNT(*) FROM receipts 
            WHERE EXTRACT(YEAR FROM receipt_date) = %s 
            AND (gross_amount IS NULL OR gross_amount = 0)
        """, (year,))
        missing_count = cur.fetchone()[0]
        
        f.write(f"Receipts entered: {cur.rowcount + missing_count:,}\n")
        f.write(f"Receipts missing amount: {missing_count:,}\n\n")
        
        if missing_count > 0:
            f.write("⚠️ IMPORTANT: You have receipts without amounts entered.\n")
            f.write("Entering these could REDUCE your tax liability.\n\n")
            f.write("Example: If 100 receipts average $50 each:\n")
            f.write("  Additional deductions: $5,000\n")
            f.write("  Tax savings (25% rate): $1,250\n\n")
        
        # TAX CALCULATION
        f.write("=" * 80 + "\n")
        f.write("ESTIMATED TAX LIABILITY\n")
        f.write("=" * 80 + "\n\n")
        
        small_business_rate = Decimal("0.11")  # Alberta small business rate ~11%
        general_rate = Decimal("0.23")  # General corporate rate ~23%
        small_business_limit = Decimal("500000")
        
        if net_income > 0:
            if net_income <= small_business_limit:
                tax = net_income * small_business_rate
                f.write(f"Net Income: ${net_income:,.2f}\n")
                f.write(f"Tax Rate: {small_business_rate * 100:.0f}% (Small Business)\n")
                f.write(f"ESTIMATED TAX OWING: ${tax:,.2f}\n\n")
            else:
                tax_low = small_business_limit * small_business_rate
                tax_high = (net_income - small_business_limit) * general_rate
                total_tax = tax_low + tax_high
                f.write(f"First $500,000 @ 11%: ${tax_low:,.2f}\n")
                f.write(f"Over $500,000 @ 23%: ${tax_high:,.2f}\n")
                f.write(f"TOTAL TAX OWING: ${total_tax:,.2f}\n\n")
        else:
            f.write("Net Loss: No tax owing\n")
            f.write(f"Loss can be carried forward/back: ${abs(net_income):,.2f}\n\n")
        
        # PAYROLL TAXES
        f.write("=" * 80 + "\n")
        f.write("PAYROLL TAXES REMITTED (Already Paid via PD7A)\n")
        f.write("=" * 80 + "\n\n")
        
        # Read PD7A data
        try:
            import json
            with open('reports/PD7A_SUMMARY_REPORT.json', 'r') as pd7a:
                pd7a_data = json.load(pd7a)
                if str(year) in pd7a_data['by_year']:
                    year_data = pd7a_data['by_year'][str(year)]
                    f.write(f"Gross Payroll: ${year_data['gross_payroll']}\n")
                    f.write(f"Tax Deductions: ${year_data['tax_deductions']}\n")
                    f.write(f"CPP (employer): ${year_data['cpp_company']}\n")
                    f.write(f"EI (employer): ${year_data['ei_company']}\n")
                    total_payroll_tax = (Decimal(year_data['tax_deductions']) + 
                                       Decimal(year_data['cpp_company']) + 
                                       Decimal(year_data['ei_company']))
                    f.write(f"TOTAL PAYROLL TAXES REMITTED: ${total_payroll_tax:,.2f}\n\n")
                    f.write("Note: Payroll taxes are already paid monthly via PD7A.\n")
                    f.write("These are SEPARATE from T2 corporate income tax.\n\n")
        except:
            f.write("PD7A data not available\n\n")
        
        # RECOMMENDATIONS
        f.write("=" * 80 + "\n")
        f.write("RECOMMENDATIONS\n")
        f.write("=" * 80 + "\n\n")
        
        f.write("1. ENTER ALL RECEIPTS\n")
        f.write("   Every dollar of business expenses REDUCES your tax bill.\n")
        f.write(f"   At 11% tax rate: $1,000 expenses = $110 tax savings\n")
        f.write(f"   At 23% tax rate: $1,000 expenses = $230 tax savings\n\n")
        
        f.write("2. COMMON DEDUCTIBLE EXPENSES\n")
        f.write("   - Vehicle fuel, maintenance, insurance\n")
        f.write("   - Office supplies, software, advertising\n")
        f.write("   - Professional fees (accounting, legal)\n")
        f.write("   - Business insurance\n")
        f.write("   - Bank fees, interest\n")
        f.write("   - Employee wages (deducted from revenue)\n\n")
        
        f.write("3. NON-DEDUCTIBLE ITEMS\n")
        f.write("   - Personal expenses\n")
        f.write("   - Fines and penalties\n")
        f.write("   - 50% of meals/entertainment\n\n")
        
        f.write("4. NEXT STEPS\n")
        f.write("   - Enter remaining receipts into database\n")
        f.write("   - Review expense categorization\n")
        f.write("   - Consult accountant for T2 filing\n")
        f.write("   - File T2 return by 6 months after fiscal year end\n\n")
        
        f.write("=" * 80 + "\n")
        f.write("END OF REPORT\n")
        f.write("=" * 80 + "\n")
    
    print("=" * 80)
    print(f"T2 TAX SUMMARY GENERATED FOR {year}")
    print("=" * 80)
    print(f"\n✓ Report saved to: {report_file}")
    print(f"\nKey findings:")
    print(f"  Net Revenue: ${revenue[3] or 0:,.2f}")
    print(f"  Total Expenses: ${total_expenses:,.2f}")
    print(f"  Net Income: ${net_income:,.2f}")
    print(f"\n⚠️ IMPORTANT: Every receipt you enter REDUCES your taxes!")
    print(f"  Missing receipts: {missing_count:,}")
    print(f"  Estimated tax rate: 11-23%")
    print(f"\nEnter your receipts to maximize deductions and minimize tax owing.")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
