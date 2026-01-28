#!/usr/bin/env python3
"""
Historical CRA Tax Analysis (2012-2020)
Complete tax analysis for Arrow Limousine's earlier operating years
"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata', 
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("🇨🇦 HISTORICAL CRA TAX ANALYSIS (2012-2020)")
print("=" * 50)

# Analyze years 2012-2020
years = list(range(2012, 2021))  # 2012 through 2020

print("📊 BUSINESS PERFORMANCE BY YEAR:")
print("=" * 40)
print("Year    Revenue      Expenses     Payroll      Net Income   GST Position")
print("-" * 75)

gst_rate = 0.05  # 5% GST in Saskatchewan
total_historical_revenue = 0
total_historical_expenses = 0
total_historical_payroll = 0
total_gst_collected = 0
total_gst_recoverable = 0

year_summaries = []

for year in years:
    # Get revenue for the year
    cur.execute("""
        SELECT SUM(amount) FROM payments 
        WHERE EXTRACT(YEAR FROM payment_date) = %s AND amount > 0
    """, (year,))
    revenue = cur.fetchone()[0] or 0
    
    # Get expenses for the year
    cur.execute("""
        SELECT SUM(gross_amount), SUM(gst_amount) FROM receipts 
        WHERE EXTRACT(YEAR FROM receipt_date) = %s AND gross_amount > 0
    """, (year,))
    expense_data = cur.fetchone()
    expenses = expense_data[0] or 0
    gst_recoverable = expense_data[1] or 0
    
    # Get payroll for the year
    cur.execute("""
        SELECT SUM(gross_pay), COUNT(*) as payroll_entries FROM driver_payroll WHERE year = %s
    """, (year,))
    payroll_data = cur.fetchone()
    payroll = payroll_data[0] or 0
    payroll_entries = payroll_data[1] or 0
    
    # Calculate totals
    total_expenses_year = float(expenses) + float(payroll)
    net_income = float(revenue) - total_expenses_year
    
    # GST calculation (GST is included in revenue)
    gst_collected = float(revenue) * gst_rate / (1 + gst_rate) if revenue > 0 else 0
    net_gst = gst_collected - float(gst_recoverable)
    gst_status = f"${abs(net_gst):>8,.0f} {'Owed' if net_gst > 0 else 'Refund'}"
    
    # Accumulate totals
    total_historical_revenue += float(revenue)
    total_historical_expenses += float(expenses)
    total_historical_payroll += float(payroll)
    total_gst_collected += gst_collected
    total_gst_recoverable += float(gst_recoverable)
    
    # Store for detailed analysis
    year_summaries.append({
        'year': year,
        'revenue': float(revenue),
        'expenses': float(expenses),
        'payroll': float(payroll),
        'net_income': net_income,
        'gst_net': net_gst,
        'payroll_entries': payroll_entries
    })
    
    print(f"{year}  ${revenue:>10,.0f}  ${expenses:>10,.0f}  ${payroll:>10,.0f}  ${net_income:>10,.0f}  {gst_status}")

# Overall historical summary
print("\n" + "=" * 75)
total_net_income = total_historical_revenue - total_historical_expenses - total_historical_payroll
total_net_gst = total_gst_collected - total_gst_recoverable

print(f"TOTAL ${total_historical_revenue:>10,.0f}  ${total_historical_expenses:>10,.0f}  ${total_historical_payroll:>10,.0f}  ${total_net_income:>10,.0f}  ${abs(total_net_gst):>8,.0f} {'Owed' if total_net_gst > 0 else 'Refund'}")

# Detailed analysis by period
print(f"\n📈 BUSINESS EVOLUTION ANALYSIS:")
print("=" * 35)

early_period = [s for s in year_summaries if 2012 <= s['year'] <= 2014]
middle_period = [s for s in year_summaries if 2015 <= s['year'] <= 2017] 
later_period = [s for s in year_summaries if 2018 <= s['year'] <= 2020]

def analyze_period(period, name):
    if not period:
        return
    
    total_rev = sum(s['revenue'] for s in period)
    total_exp = sum(s['expenses'] + s['payroll'] for s in period)
    total_net = total_rev - total_exp
    avg_net = total_net / len(period)
    
    print(f"\n{name} ({period[0]['year']}-{period[-1]['year']}):")
    print(f"  Total Revenue: ${total_rev:,.0f}")
    print(f"  Total Expenses: ${total_exp:,.0f}")
    print(f"  Net Result: ${total_net:,.0f}")
    print(f"  Average Annual Net: ${avg_net:,.0f}")
    
    if total_net > 0:
        print(f"  Status: PROFITABLE period")
    else:
        print(f"  Status: LOSS period")

analyze_period(early_period, "Early Operations")
analyze_period(middle_period, "Growth Period") 
analyze_period(later_period, "Recent Pre-COVID")

# Cash flow analysis for key years
print(f"\n💰 KEY YEAR CASH FLOW DETAILS:")
print("=" * 35)

key_years = [2012, 2014, 2016, 2018, 2020]
for year in key_years:
    year_data = next((s for s in year_summaries if s['year'] == year), None)
    if year_data:
        print(f"\n{year} Detailed Breakdown:")
        print(f"  Revenue: ${year_data['revenue']:,.0f}")
        print(f"  Receipt Expenses: ${year_data['expenses']:,.0f}")
        print(f"  Driver Payroll: ${year_data['payroll']:,.0f} ({year_data['payroll_entries']} entries)")
        print(f"  Net Income: ${year_data['net_income']:,.0f}")
        
        if year_data['net_income'] > 0:
            # Calculate estimated tax for profitable years
            estimated_tax = year_data['net_income'] * 0.115  # 11.5% small business rate
            print(f"  Estimated Income Tax: ${estimated_tax:,.0f}")
        else:
            print(f"  Tax Status: Loss carryforward of ${abs(year_data['net_income']):,.0f}")

# GST analysis
print(f"\n💹 HISTORICAL GST SUMMARY (2012-2020):")
print("=" * 40)
print(f"Total GST Collected on Sales: ${total_gst_collected:,.2f}")
print(f"Total GST Recoverable on Expenses: ${total_gst_recoverable:,.2f}")
print(f"Net GST Position: ${abs(total_net_gst):,.2f} {'OWED' if total_net_gst > 0 else 'REFUND'}")

# Profitable vs loss years
profitable_years = [s for s in year_summaries if s['net_income'] > 0]
loss_years = [s for s in year_summaries if s['net_income'] <= 0]

print(f"\n📊 PROFITABILITY ANALYSIS:")
print("=" * 30)
print(f"Profitable Years: {len(profitable_years)} out of {len(years)}")
if profitable_years:
    profitable_list = [str(s['year']) for s in profitable_years]
    total_profits = sum(s['net_income'] for s in profitable_years)
    print(f"  Years: {', '.join(profitable_list)}")
    print(f"  Total Profits: ${total_profits:,.0f}")

print(f"Loss Years: {len(loss_years)} out of {len(years)}")
if loss_years:
    loss_list = [str(s['year']) for s in loss_years]
    total_losses = sum(abs(s['net_income']) for s in loss_years)
    print(f"  Years: {', '.join(loss_list)}")
    print(f"  Total Losses: ${total_losses:,.0f}")

cur.close()
conn.close()

print(f"\n🎯 HISTORICAL CRA IMPLICATIONS:")
print("=" * 35)
print(f"• 2012-2020 Net Business Result: ${total_net_income:,.0f}")
if total_net_income < 0:
    print(f"• Cumulative Business Loss: ${abs(total_net_income):,.0f}")
    print(f"• Loss Carryforward Available: Significant tax benefits for future profits")
else:
    print(f"• Cumulative Business Profit: ${total_net_income:,.0f}")
    print(f"• Historical Tax Obligations: Income tax would apply")

print(f"• GST Net Position: ${abs(total_net_gst):,.0f} {'owed to CRA' if total_net_gst > 0 else 'refundable from CRA'}")
print(f"• Business operated through multiple economic cycles")
print(f"• Comprehensive expense documentation supports CRA compliance")