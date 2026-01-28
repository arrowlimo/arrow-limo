#!/usr/bin/env python3
"""
Generate beverage cost recovery analysis report.
Compare what we spent on beverages (5310) vs what we recovered (4115).
"""

import psycopg2
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("="*80)
    print("BEVERAGE COST RECOVERY ANALYSIS")
    print("="*80)
    
    # Get beverage costs (5310) by year
    print("\n1. Beverage Costs (Account 5310 - Customer Beverages)")
    print("-"*80)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as receipt_count,
            SUM(gross_amount) as total_cost,
            AVG(gross_amount) as avg_cost
        FROM receipts
        WHERE gl_account_code = '5310'
        AND receipt_date IS NOT NULL
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    
    costs_by_year = {}
    total_cost = 0
    
    for row in cur.fetchall():
        year = int(row[0]) if row[0] else 0
        count = row[1]
        cost = float(row[2]) if row[2] else 0
        avg = float(row[3]) if row[3] else 0
        
        costs_by_year[year] = cost
        total_cost += cost
        
        print(f"  {year}: {count:3d} receipts = ${cost:12,.2f} (avg ${avg:6,.2f})")
    
    print(f"\n  TOTAL BEVERAGE COSTS: ${total_cost:12,.2f}")
    
    # Get beverage revenue (4115) by year
    print("\n2. Beverage Revenue Recovery (Account 4115 - Beverage Service Charges)")
    print("-"*80)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as receipt_count,
            SUM(gross_amount) as total_revenue,
            AVG(gross_amount) as avg_revenue
        FROM receipts
        WHERE gl_account_code = '4115'
        AND receipt_date IS NOT NULL
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    
    revenue_by_year = {}
    total_revenue = 0
    
    for row in cur.fetchall():
        year = int(row[0]) if row[0] else 0
        count = row[1]
        revenue = float(row[2]) if row[2] else 0
        avg = float(row[3]) if row[3] else 0
        
        revenue_by_year[year] = revenue
        total_revenue += revenue
        
        print(f"  {year}: {count:3d} receipts = ${revenue:12,.2f} (avg ${avg:6,.2f})")
    
    print(f"\n  TOTAL BEVERAGE REVENUE: ${total_revenue:12,.2f}")
    
    # Calculate recovery rate
    print("\n3. Cost Recovery Analysis")
    print("="*80)
    
    all_years = sorted(set(list(costs_by_year.keys()) + list(revenue_by_year.keys())))
    
    for year in all_years:
        if year == 0:
            continue
            
        cost = costs_by_year.get(year, 0)
        revenue = revenue_by_year.get(year, 0)
        recovery = (revenue / cost * 100) if cost > 0 else 0
        shortfall = cost - revenue
        
        print(f"\n  {year}:")
        print(f"    Costs:    ${cost:12,.2f}")
        print(f"    Revenue:  ${revenue:12,.2f}")
        print(f"    Recovery: {recovery:6.1f}%")
        
        if shortfall > 0:
            print(f"    Shortfall: ${shortfall:12,.2f} ⚠️ UNDERCHARGING")
        else:
            print(f"    Surplus:   ${-shortfall:12,.2f} ✓ PROFITABLE")
    
    # Overall analysis
    print("\n4. OVERALL SUMMARY")
    print("="*80)
    
    overall_recovery = (total_revenue / total_cost * 100) if total_cost > 0 else 0
    overall_shortfall = total_cost - total_revenue
    
    print(f"  Total Costs:    ${total_cost:12,.2f}")
    print(f"  Total Revenue:  ${total_revenue:12,.2f}")
    print(f"  Recovery Rate:  {overall_recovery:6.1f}%")
    
    if overall_shortfall > 0:
        print(f"\n  ⚠️  UNDERCHARGING by ${overall_shortfall:,.2f}")
        print(f"  Recommendation: Increase beverage service charges to recover costs")
    elif overall_shortfall < 0:
        print(f"\n  ✓ PROFITABLE by ${-overall_shortfall:,.2f}")
        print(f"  Beverage service charges exceed costs")
    else:
        print(f"\n  ✓ BREAK-EVEN on beverage costs")
    
    # Check categorization status
    print("\n5. Data Completeness Check")
    print("-"*80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN gl_account_code = '5310' THEN 1 END) as costs,
            COUNT(CASE WHEN gl_account_code = '4115' THEN 1 END) as revenue,
            COUNT(CASE WHEN gl_account_code IN ('5310', '4115') THEN 1 END) as beverage_total
        FROM receipts
        WHERE category LIKE '%beverage%' OR description LIKE '%beverage%'
        OR vendor_name LIKE '%costco%' OR vendor_name LIKE '%liquor%'
    """)
    
    row = cur.fetchone()
    print(f"  Potential beverage receipts: {row[0]}")
    print(f"  Categorized as 5310 (costs): {row[1]}")
    print(f"  Categorized as 4115 (revenue): {row[2]}")
    print(f"  Total categorized: {row[3]}")
    
    if row[0] > row[3]:
        print(f"\n  ⚠️  {row[0] - row[3]} receipts may need categorization")
        print(f"  Run: python smart_expense_categorization.py --write")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
