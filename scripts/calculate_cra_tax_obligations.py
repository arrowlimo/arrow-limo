#!/usr/bin/env python3
"""
CRA Tax Calculation Analysis
Calculates total business income, expenses, and tax obligations for Arrow Limousine
"""

import psycopg2
from datetime import datetime

def main():
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata', 
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()

    # Get current tax year (2024 for filing in 2025)
    tax_year = 2024

    print(f"🇨🇦 CRA TAX CALCULATION REPORT - {tax_year}")
    print("=" * 50)

    # BUSINESS INCOME CALCULATION
    print(f"💰 BUSINESS INCOME ({tax_year}):")
    print("=" * 30)

    # Total charter revenue
    cur.execute("""
        SELECT COUNT(*) as charter_count,
               SUM(total_amount_due) as gross_revenue,
               SUM(paid_amount) as revenue_collected
        FROM charters 
        WHERE EXTRACT(YEAR FROM charter_date) = %s
          AND total_amount_due > 0
    """, (tax_year,))
    
    charter_income = cur.fetchone()
    charter_count, gross_revenue, collected = charter_income
    gross_revenue = gross_revenue or 0
    collected = collected or 0
    
    print(f"Charter Services:")
    print(f"  {charter_count:,} charters completed")
    print(f"  Gross Revenue: ${gross_revenue:,.2f}")
    print(f"  Revenue Collected: ${collected:,.2f}")

    # Payment processing revenue
    cur.execute("""
        SELECT COUNT(*) as payment_count,
               SUM(amount) as total_payments
        FROM payments 
        WHERE EXTRACT(YEAR FROM payment_date) = %s
          AND amount > 0
    """, (tax_year,))
    
    payment_income = cur.fetchone()
    payment_count, total_payments = payment_income
    total_payments = total_payments or 0
    
    print(f"\nPayment Processing:")
    print(f"  {payment_count:,} payments received")
    print(f"  Total Payments: ${total_payments:,.2f}")

    # BUSINESS EXPENSES CALCULATION
    print(f"\n💸 BUSINESS EXPENSES ({tax_year}):")
    print("=" * 35)

    # Major expense categories for CRA
    expense_categories = [
        ("Vehicle Fuel", ["shell", "petro", "esso", "gas", "fuel"]),
        ("Vehicle Maintenance", ["tire", "oil", "repair", "maintenance", "canadian tire"]),
        ("Insurance", ["insurance", "aviva", "sgi", "premium"]),
        ("Vehicle Financing", ["heffner", "financing", "lease", "loan"]),
        ("Office Expenses", ["office", "supplies", "rent", "utilities"]),
        ("Communication", ["phone", "internet", "sasktel", "rogers"]),
        ("Professional Fees", ["accounting", "legal", "professional"]),
    ]

    total_expenses = 0
    total_gst_recoverable = 0

    for category, keywords in expense_categories:
        # Build the WHERE clause for keywords
        keyword_conditions = " OR ".join([f"LOWER(vendor_name) LIKE '%{kw}%' OR LOWER(description) LIKE '%{kw}%'" for kw in keywords])
        
        query = f"""
            SELECT COUNT(*) as expense_count,
                   SUM(gross_amount) as total_expense,
                   SUM(gst_amount) as total_gst
            FROM receipts 
            WHERE EXTRACT(YEAR FROM receipt_date) = {tax_year}
              AND ({keyword_conditions})
              AND gross_amount > 0
        """
        cur.execute(query)
        
        category_expense = cur.fetchone()
        count, expense, gst = category_expense
        expense = expense or 0
        gst = gst or 0
        
        if expense > 0:
            print(f"{category}:")
            print(f"  {count} receipts, ${expense:,.2f} (GST: ${gst:,.2f})")
            total_expenses += expense
            total_gst_recoverable += gst

    # Driver payroll expenses
    cur.execute("""
        SELECT COUNT(*) as payroll_count,
               SUM(gross_pay) as total_wages,
               SUM(cpp + ei + tax) as total_deductions
        FROM driver_payroll 
        WHERE year = %s
    """, (tax_year,))
    
    payroll_expense = cur.fetchone()
    payroll_count, wages, deductions = payroll_expense
    wages = wages or 0
    deductions = deductions or 0
    
    if wages > 0:
        print(f"Driver Wages:")
        print(f"  {payroll_count} payroll entries")
        print(f"  Gross Wages: ${wages:,.2f}")
        print(f"  Deductions Paid: ${deductions:,.2f}")
        total_expenses += wages

    # CRA TAX CALCULATION
    print(f"\n🧮 CRA TAX CALCULATION ({tax_year}):")
    print("=" * 40)

    net_business_income = float(max(gross_revenue, total_payments)) - float(total_expenses)
    
    print(f"Gross Business Income: ${float(max(gross_revenue, total_payments)):,.2f}")
    print(f"Total Business Expenses: ${float(total_expenses):,.2f}")
    print(f"Net Business Income: ${net_business_income:,.2f}")
    print(f"GST Recoverable: ${float(total_gst_recoverable):,.2f}")

    # GST/HST Calculation (Saskatchewan = 5% GST + 6% PST = 11% total)
    # Business should collect GST on services and can recover GST on expenses
    gst_rate = 0.05  # 5% GST in Saskatchewan
    
    # GST collected on charter services (included in revenue)
    gst_collected = float(gross_revenue) * gst_rate / (1 + gst_rate)
    
    # Net GST position
    net_gst_owed = gst_collected - float(total_gst_recoverable)
    
    print(f"\n💹 GST/HST CALCULATION:")
    print("=" * 25)
    print(f"GST Collected on Sales: ${gst_collected:,.2f}")
    print(f"GST Recoverable on Expenses: ${float(total_gst_recoverable):,.2f}")
    print(f"Net GST {'Owed' if net_gst_owed > 0 else 'Refund'}: ${abs(net_gst_owed):,.2f}")

    # Income tax estimation (simplified)
    if net_business_income > 0:
        # Saskatchewan small business tax rate ~11.5% (federal 9% + provincial 2.5%)
        small_business_rate = 0.115
        estimated_income_tax = net_business_income * small_business_rate
        
        print(f"\n📋 INCOME TAX ESTIMATION:")
        print("=" * 30)
        print(f"Net Business Income: ${net_business_income:,.2f}")
        print(f"Small Business Tax Rate: {small_business_rate:.1%}")
        print(f"Estimated Income Tax: ${estimated_income_tax:,.2f}")
        
        # Total tax obligation
        total_tax_owed = net_gst_owed + estimated_income_tax
        print(f"\n🎯 TOTAL CRA OBLIGATION:")
        print("=" * 25)
        print(f"GST {'Owed' if net_gst_owed > 0 else 'Refund'}: ${net_gst_owed:,.2f}")
        print(f"Income Tax Owed: ${estimated_income_tax:,.2f}")
        print(f"TOTAL {'OWED' if total_tax_owed > 0 else 'REFUND'}: ${abs(total_tax_owed):,.2f}")
    
    else:
        print(f"\n📋 TAX LOSS SITUATION:")
        print("=" * 25)
        print(f"Business Loss: ${abs(net_business_income):,.2f}")
        print(f"No Income Tax Owed (Loss Carryforward Available)")
        print(f"GST {'Owed' if net_gst_owed > 0 else 'Refund'}: ${abs(net_gst_owed):,.2f}")

    # T4 Summary for employees
    print(f"\n👥 PAYROLL TAX SUMMARY ({tax_year}):")
    print("=" * 35)
    
    cur.execute("""
        SELECT COUNT(DISTINCT employee_id) as employee_count,
               SUM(t4_box_14) as total_employment_income,
               SUM(t4_box_16) as total_cpp,
               SUM(t4_box_18) as total_ei,
               SUM(t4_box_22) as total_tax_withheld
        FROM driver_payroll 
        WHERE year = %s
          AND employee_id IS NOT NULL
    """, (tax_year,))
    
    t4_summary = cur.fetchone()
    emp_count, emp_income, cpp, ei, tax_withheld = t4_summary
    emp_income = emp_income or 0
    cpp = cpp or 0
    ei = ei or 0
    tax_withheld = tax_withheld or 0
    
    print(f"Employees: {emp_count or 0}")
    print(f"Total T4 Employment Income: ${emp_income:,.2f}")
    print(f"CPP Contributions: ${cpp:,.2f}")
    print(f"EI Contributions: ${ei:,.2f}")
    print(f"Income Tax Withheld: ${tax_withheld:,.2f}")

    # Employer obligations
    employer_cpp = cpp  # Employer matches employee CPP
    employer_ei = ei * 1.4  # Employer pays 1.4x employee EI
    
    print(f"\nEmployer Obligations:")
    print(f"Employer CPP: ${employer_cpp:,.2f}")
    print(f"Employer EI: ${employer_ei:,.2f}")
    print(f"Total Payroll Remittances: ${cpp + ei + tax_withheld + employer_cpp + employer_ei:,.2f}")

    cur.close()
    conn.close()

    print(f"\n[WARN]  IMPORTANT NOTES:")
    print("=" * 20)
    print("• This is an ESTIMATE based on available data")
    print("• Consult with qualified accountant for official filing")
    print("• Additional deductions may apply (depreciation, etc.)")
    print("• GST filing frequency depends on annual revenue")
    print("• Installment payments may be required for large amounts")

if __name__ == "__main__":
    main()