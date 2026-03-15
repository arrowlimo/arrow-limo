#!/usr/bin/env python3
"""
CHARTER REVENUE vs VEHICLE OPERATING COSTS ANALYSIS
===================================================

Analyzes charter revenue (excluding beverage premiums) versus all vehicle-related
expenses including fuel, maintenance, leasing, and insurance by year.
"""

import os
import psycopg2
from datetime import datetime
import re

# Database connection
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'almsdata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '***REDACTED***')

def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def analyze_charter_revenue_vs_vehicle_costs():
    """Analyze charter revenue versus vehicle operating costs by year."""
    
    print("🚗 CHARTER REVENUE vs VEHICLE OPERATING COSTS ANALYSIS")
    print("=" * 60)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get charter revenue by year (excluding beverage premium)
    print("\n💰 CHARTER REVENUE BY YEAR (Excluding Beverages):")
    print("-" * 50)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM charter_date) as year,
            COUNT(*) as total_charters,
            SUM(rate) as total_revenue,
            AVG(rate) as avg_rate,
            COUNT(CASE WHEN rate >= 1000 THEN 1 END) as premium_charters,
            SUM(CASE WHEN rate >= 1000 THEN rate END) as premium_revenue,
            AVG(CASE WHEN rate >= 1000 THEN rate END) as avg_premium_rate,
            AVG(CASE WHEN rate < 1000 THEN rate END) as avg_standard_rate
        FROM charters
        WHERE charter_date IS NOT NULL AND rate > 0
        GROUP BY EXTRACT(YEAR FROM charter_date)
        ORDER BY year
    """)
    
    charter_revenue_data = cur.fetchall()
    
    # Calculate adjusted revenue (removing estimated beverage premium)
    adjusted_revenue_by_year = {}
    
    for year, total_charters, total_rev, avg_rate, premium_count, premium_rev, avg_premium, avg_standard in charter_revenue_data:
        year = int(year)
        total_rev = float(total_rev or 0)
        premium_rev = float(premium_rev or 0)
        
        # Estimate beverage premium (30% of premium over standard rate difference)
        if avg_premium and avg_standard and premium_count:
            rate_premium = float(avg_premium) - float(avg_standard)
            estimated_beverage_premium = rate_premium * premium_count * 0.3
        else:
            estimated_beverage_premium = 0
        
        # Adjust revenue by removing beverage premium
        adjusted_revenue = total_rev - estimated_beverage_premium
        adjusted_revenue_by_year[year] = {
            'total_charters': total_charters,
            'total_revenue': total_rev,
            'beverage_premium': estimated_beverage_premium,
            'adjusted_revenue': adjusted_revenue,
            'avg_rate': float(avg_rate or 0)
        }
        
        print(f"   {year}: {total_charters:,} charters")
        print(f"        Total Revenue: ${total_rev:,.2f}")
        print(f"        Est. Beverage Premium: ${estimated_beverage_premium:,.2f}")
        print(f"        Adjusted Revenue: ${adjusted_revenue:,.2f}")
        print(f"        Avg Rate: ${float(avg_rate or 0):.2f}")
        print()
    
    # Get vehicle fuel costs by year
    print(f"\n⛽ VEHICLE FUEL COSTS BY YEAR:")
    print("-" * 33)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as fuel_purchases,
            SUM(gross_amount) as total_fuel_cost,
            SUM(gst_amount) as fuel_gst,
            AVG(gross_amount) as avg_fuel_purchase
        FROM receipts
        WHERE (
            LOWER(vendor_name) LIKE '%shell%' OR
            LOWER(vendor_name) LIKE '%petro%' OR
            LOWER(vendor_name) LIKE '%esso%' OR
            LOWER(vendor_name) LIKE '%fas gas%' OR
            LOWER(vendor_name) LIKE '%chevron%' OR
            LOWER(vendor_name) LIKE '%husky%' OR
            LOWER(vendor_name) LIKE '%mohawk%' OR
            LOWER(vendor_name) LIKE '%co-op%' OR
            LOWER(vendor_name) LIKE '%gas%' OR
            LOWER(description) LIKE '%fuel%' OR
            LOWER(description) LIKE '%gas%' OR
            LOWER(description) LIKE '%diesel%' OR
            LOWER(category) LIKE '%fuel%' OR
            LOWER(category) LIKE '%gas%'
        )
        AND receipt_date IS NOT NULL
        AND gross_amount > 0
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    
    fuel_costs = {int(row[0]): row for row in cur.fetchall()}
    
    for year, data in fuel_costs.items():
        year_data, purchases, cost, gst, avg = data
        print(f"   {year}: {purchases} purchases, ${float(cost):,.2f}")
        print(f"        GST: ${float(gst or 0):.2f}, Avg: ${float(avg):.2f}")
        print()
    
    # Get vehicle maintenance costs by year
    print(f"\n🔧 VEHICLE MAINTENANCE COSTS BY YEAR:")
    print("-" * 38)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as maintenance_receipts,
            SUM(gross_amount) as total_maintenance_cost,
            AVG(gross_amount) as avg_maintenance_cost
        FROM receipts
        WHERE (
            LOWER(vendor_name) LIKE '%tire%' OR
            LOWER(vendor_name) LIKE '%automotive%' OR
            LOWER(vendor_name) LIKE '%mechanic%' OR
            LOWER(vendor_name) LIKE '%repair%' OR
            LOWER(vendor_name) LIKE '%service%' OR
            LOWER(vendor_name) LIKE '%canadian tire%' OR
            LOWER(vendor_name) LIKE '%jiffy lube%' OR
            LOWER(vendor_name) LIKE '%midas%' OR
            LOWER(vendor_name) LIKE '%kal tire%' OR
            LOWER(vendor_name) LIKE '%motomaster%' OR
            LOWER(description) LIKE '%repair%' OR
            LOWER(description) LIKE '%maintenance%' OR
            LOWER(description) LIKE '%service%' OR
            LOWER(description) LIKE '%oil change%' OR
            LOWER(description) LIKE '%tire%' OR
            LOWER(category) LIKE '%maintenance%' OR
            LOWER(category) LIKE '%repair%' OR
            LOWER(category) LIKE '%automotive%'
        )
        AND receipt_date IS NOT NULL
        AND gross_amount > 0
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    
    maintenance_costs = {int(row[0]): row for row in cur.fetchall()}
    
    for year, data in maintenance_costs.items():
        year_data, receipts, cost, avg = data
        print(f"   {year}: {receipts} receipts, ${float(cost):,.2f}")
        print(f"        Average: ${float(avg):.2f}")
        print()
    
    # Get vehicle lease/financing costs by year
    print(f"\n🏦 VEHICLE LEASE/FINANCING COSTS BY YEAR:")
    print("-" * 43)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as lease_payments,
            SUM(gross_amount) as total_lease_cost,
            AVG(gross_amount) as avg_lease_payment,
            STRING_AGG(DISTINCT vendor_name, ', ') as lease_vendors
        FROM receipts
        WHERE (
            LOWER(vendor_name) LIKE '%heffner%' OR
            LOWER(vendor_name) LIKE '%financing%' OR
            LOWER(vendor_name) LIKE '%lease%' OR
            LOWER(vendor_name) LIKE '%auto finance%' OR
            LOWER(vendor_name) LIKE '%woodridge%' OR
            LOWER(vendor_name) LIKE '%infiniti%' OR
            LOWER(description) LIKE '%lease%' OR
            LOWER(description) LIKE '%financing%' OR
            LOWER(description) LIKE '%loan%' OR
            LOWER(description) LIKE '%payment%' OR
            LOWER(category) LIKE '%lease%' OR
            LOWER(category) LIKE '%financing%'
        )
        AND receipt_date IS NOT NULL
        AND gross_amount > 0
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    
    lease_costs = {int(row[0]): row for row in cur.fetchall()}
    
    for year, data in lease_costs.items():
        year_data, payments, cost, avg, vendors = data
        print(f"   {year}: {payments} payments, ${float(cost):,.2f}")
        print(f"        Average: ${float(avg):.2f}")
        print(f"        Vendors: {vendors[:60]}{'...' if len(vendors) > 60 else ''}")
        print()
    
    # Get vehicle insurance costs by year
    print(f"\n🛡️ VEHICLE INSURANCE COSTS BY YEAR:")
    print("-" * 36)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as insurance_payments,
            SUM(gross_amount) as total_insurance_cost,
            AVG(gross_amount) as avg_insurance_payment,
            STRING_AGG(DISTINCT vendor_name, ', ') as insurance_vendors
        FROM receipts
        WHERE (
            LOWER(vendor_name) LIKE '%insurance%' OR
            LOWER(vendor_name) LIKE '%aviva%' OR
            LOWER(vendor_name) LIKE '%sgi%' OR
            LOWER(vendor_name) LIKE '%broker%' OR
            LOWER(description) LIKE '%insurance%' OR
            LOWER(description) LIKE '%premium%' OR
            LOWER(description) LIKE '%policy%' OR
            LOWER(category) LIKE '%insurance%'
        )
        AND receipt_date IS NOT NULL
        AND gross_amount > 0
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    
    insurance_costs = {int(row[0]): row for row in cur.fetchall()}
    
    for year, data in insurance_costs.items():
        year_data, payments, cost, avg, vendors = data
        print(f"   {year}: {payments} payments, ${float(cost):,.2f}")
        print(f"        Average: ${float(avg):.2f}")
        print(f"        Vendors: {vendors[:60]}{'...' if len(vendors) > 60 else ''}")
        print()
    
    # Calculate comprehensive year-by-year analysis
    print(f"\n📊 COMPREHENSIVE REVENUE vs VEHICLE COSTS ANALYSIS:")
    print("-" * 54)
    
    all_years = sorted(set(
        list(adjusted_revenue_by_year.keys()) +
        list(fuel_costs.keys()) +
        list(maintenance_costs.keys()) +
        list(lease_costs.keys()) +
        list(insurance_costs.keys())
    ))
    
    total_revenue = 0
    total_fuel = 0
    total_maintenance = 0
    total_lease = 0
    total_insurance = 0
    total_vehicle_costs = 0
    
    print("\n   YEAR | REVENUE    | FUEL      | MAINT     | LEASE     | INSUR     | TOTAL COSTS | NET PROFIT")
    print("   -----|------------|-----------|-----------|-----------|-----------|-------------|------------")
    
    for year in all_years:
        # Revenue data
        revenue_data = adjusted_revenue_by_year.get(year, {})
        revenue = revenue_data.get('adjusted_revenue', 0)
        
        # Cost data
        fuel_cost = float(fuel_costs.get(year, (0, 0, 0, 0, 0))[2] or 0)
        maint_cost = float(maintenance_costs.get(year, (0, 0, 0, 0))[2] or 0)
        lease_cost = float(lease_costs.get(year, (0, 0, 0, 0, ''))[2] or 0)
        insurance_cost = float(insurance_costs.get(year, (0, 0, 0, 0, ''))[2] or 0)
        
        year_vehicle_costs = fuel_cost + maint_cost + lease_cost + insurance_cost
        net_profit = revenue - year_vehicle_costs
        
        # Update totals
        total_revenue += revenue
        total_fuel += fuel_cost
        total_maintenance += maint_cost
        total_lease += lease_cost
        total_insurance += insurance_cost
        total_vehicle_costs += year_vehicle_costs
        
        print(f"   {year} | ${revenue:9,.0f} | ${fuel_cost:8,.0f} | ${maint_cost:8,.0f} | ${lease_cost:8,.0f} | ${insurance_cost:8,.0f} | ${year_vehicle_costs:10,.0f} | ${net_profit:10,.0f}")
    
    print("   -----|------------|-----------|-----------|-----------|-----------|-------------|------------")
    print(f"  TOTAL | ${total_revenue:9,.0f} | ${total_fuel:8,.0f} | ${total_maintenance:8,.0f} | ${total_lease:8,.0f} | ${total_insurance:8,.0f} | ${total_vehicle_costs:10,.0f} | ${total_revenue - total_vehicle_costs:10,.0f}")
    
    # Calculate percentages and ratios
    print(f"\n🎯 BUSINESS PERFORMANCE METRICS:")
    print("-" * 35)
    
    if total_revenue > 0:
        fuel_pct = (total_fuel / total_revenue) * 100
        maint_pct = (total_maintenance / total_revenue) * 100
        lease_pct = (total_lease / total_revenue) * 100
        insurance_pct = (total_insurance / total_revenue) * 100
        total_cost_pct = (total_vehicle_costs / total_revenue) * 100
        profit_margin = ((total_revenue - total_vehicle_costs) / total_revenue) * 100
        
        print(f"   Total Charter Revenue: ${total_revenue:,.2f}")
        print(f"   Total Vehicle Costs: ${total_vehicle_costs:,.2f}")
        print(f"   Net Operating Profit: ${total_revenue - total_vehicle_costs:,.2f}")
        print()
        print(f"   Cost Breakdown (% of Revenue):")
        print(f"      Fuel: {fuel_pct:.1f}% (${total_fuel:,.2f})")
        print(f"      Maintenance: {maint_pct:.1f}% (${total_maintenance:,.2f})")
        print(f"      Lease/Financing: {lease_pct:.1f}% (${total_lease:,.2f})")
        print(f"      Insurance: {insurance_pct:.1f}% (${total_insurance:,.2f})")
        print(f"      Total Vehicle Costs: {total_cost_pct:.1f}%")
        print(f"   Operating Profit Margin: {profit_margin:.1f}%")
    
    # Identify best and worst performing years
    print(f"\n📈 BEST & WORST PERFORMING YEARS:")
    print("-" * 35)
    
    year_performance = []
    for year in all_years:
        revenue_data = adjusted_revenue_by_year.get(year, {})
        revenue = revenue_data.get('adjusted_revenue', 0)
        
        fuel_cost = float(fuel_costs.get(year, (0, 0, 0, 0, 0))[2] or 0)
        maint_cost = float(maintenance_costs.get(year, (0, 0, 0, 0))[2] or 0)
        lease_cost = float(lease_costs.get(year, (0, 0, 0, 0, ''))[2] or 0)
        insurance_cost = float(insurance_costs.get(year, (0, 0, 0, 0, ''))[2] or 0)
        
        year_vehicle_costs = fuel_cost + maint_cost + lease_cost + insurance_cost
        net_profit = revenue - year_vehicle_costs
        
        if revenue > 0:
            profit_margin = (net_profit / revenue) * 100
            year_performance.append((year, revenue, year_vehicle_costs, net_profit, profit_margin))
    
    # Sort by profit margin
    year_performance.sort(key=lambda x: x[4], reverse=True)
    
    print("   TOP 5 PROFIT MARGIN YEARS:")
    for year, revenue, costs, profit, margin in year_performance[:5]:
        print(f"      {year}: {margin:.1f}% margin (${profit:,.0f} profit on ${revenue:,.0f} revenue)")
    
    print("\n   LOWEST 5 PROFIT MARGIN YEARS:")
    for year, revenue, costs, profit, margin in year_performance[-5:]:
        print(f"      {year}: {margin:.1f}% margin (${profit:,.0f} profit on ${revenue:,.0f} revenue)")
    
    # Additional insights
    print(f"\n💡 BUSINESS INSIGHTS:")
    print("-" * 20)
    
    avg_annual_revenue = total_revenue / len(adjusted_revenue_by_year) if adjusted_revenue_by_year else 0
    avg_annual_costs = total_vehicle_costs / len(all_years) if all_years else 0
    
    print(f"   • Average Annual Revenue: ${avg_annual_revenue:,.2f}")
    print(f"   • Average Annual Vehicle Costs: ${avg_annual_costs:,.2f}")
    print(f"   • Revenue Per Dollar of Vehicle Costs: ${total_revenue/total_vehicle_costs if total_vehicle_costs > 0 else 0:.2f}")
    
    # Find years with unusual patterns
    high_fuel_years = [(year, data) for year, data in fuel_costs.items() if float(data[2]) > avg_annual_costs * 0.5]
    if high_fuel_years:
        print(f"\n   High Fuel Cost Years:")
        for year, (_, purchases, cost, gst, avg) in high_fuel_years:
            print(f"      {year}: ${float(cost):,.2f} ({purchases} purchases)")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    # Set database environment variables
    os.environ['DB_HOST'] = 'localhost'
    os.environ['DB_NAME'] = 'almsdata'
    os.environ['DB_USER'] = 'postgres'
    os.environ['DB_PASSWORD'] = '***REDACTED***'
    
    analyze_charter_revenue_vs_vehicle_costs()