#!/usr/bin/env python3
"""
ALCOHOL PURCHASE vs BEVERAGE REVENUE ANALYSIS
=============================================

Analyzes alcohol purchases from receipts versus beverage charges to clients
to determine profit margins on beverage service by year.
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

def analyze_alcohol_vs_beverage_revenue():
    """Analyze alcohol purchases vs beverage charges by year."""
    
    print("🍷 ALCOHOL PURCHASE vs BEVERAGE REVENUE ANALYSIS")
    print("=" * 55)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Find alcohol-related purchases from receipts
    print("\n🛒 ALCOHOL PURCHASES BY YEAR:")
    print("-" * 35)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as alcohol_purchases,
            SUM(gross_amount) as total_alcohol_cost,
            SUM(gst_amount) as total_gst,
            SUM(net_amount) as net_alcohol_cost,
            AVG(gross_amount) as avg_purchase,
            STRING_AGG(DISTINCT vendor_name, ', ') as vendors
        FROM receipts
        WHERE (
            LOWER(vendor_name) LIKE '%liquor%' OR
            LOWER(vendor_name) LIKE '%wine%' OR
            LOWER(vendor_name) LIKE '%beer%' OR
            LOWER(vendor_name) LIKE '%alcohol%' OR
            LOWER(vendor_name) LIKE '%spirits%' OR
            LOWER(vendor_name) LIKE '%sobeys liquor%' OR
            LOWER(vendor_name) LIKE '%co-op liquor%' OR
            LOWER(vendor_name) LIKE '%liquor store%' OR
            LOWER(description) LIKE '%alcohol%' OR
            LOWER(description) LIKE '%wine%' OR
            LOWER(description) LIKE '%beer%' OR
            LOWER(description) LIKE '%liquor%' OR
            LOWER(description) LIKE '%champagne%' OR
            LOWER(description) LIKE '%beverage%' OR
            LOWER(category) LIKE '%alcohol%' OR
            LOWER(category) LIKE '%beverage%'
        )
        AND receipt_date IS NOT NULL
        AND gross_amount > 0
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    
    alcohol_purchases = cur.fetchall()
    
    total_alcohol_cost = 0
    
    for year, purchases, cost, gst, net_cost, avg_purchase, vendors in alcohol_purchases:
        year = int(year) if year else 0
        total_alcohol_cost += (cost or 0)
        
        print(f"   {year}: {purchases} purchases, ${cost:,.2f} total cost")
        print(f"        GST: ${gst or 0:.2f}, Net: ${net_cost or 0:.2f}")
        print(f"        Average: ${avg_purchase:.2f} per purchase")
        print(f"        Vendors: {vendors[:80]}{'...' if len(vendors) > 80 else ''}")
        print()
    
    # Find beverage-related charges to clients
    print(f"\n🥂 BEVERAGE CHARGES TO CLIENTS BY YEAR:")
    print("-" * 40)
    
    # Check charter charges table for beverage services
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM c.charter_date) as year,
            COUNT(CASE WHEN cc.charge_type LIKE '%beverage%' OR 
                          cc.charge_type LIKE '%alcohol%' OR
                          cc.charge_type LIKE '%bar%' OR
                          cc.description LIKE '%beverage%' OR
                          cc.description LIKE '%alcohol%' OR
                          cc.description LIKE '%bar%' OR
                          cc.description LIKE '%wine%' OR
                          cc.description LIKE '%champagne%' THEN 1 END) as beverage_charges,
            SUM(CASE WHEN cc.charge_type LIKE '%beverage%' OR 
                          cc.charge_type LIKE '%alcohol%' OR
                          cc.charge_type LIKE '%bar%' OR
                          cc.description LIKE '%beverage%' OR
                          cc.description LIKE '%alcohol%' OR
                          cc.description LIKE '%bar%' OR
                          cc.description LIKE '%wine%' OR
                          cc.description LIKE '%champagne%' THEN cc.amount ELSE 0 END) as beverage_revenue,
            COUNT(CASE WHEN c.beverage_service_required = true THEN 1 END) as charters_with_beverage_service,
            COUNT(*) as total_charters
        FROM charters c
        LEFT JOIN charter_charges cc ON c.charter_id = cc.charter_id
        WHERE c.charter_date IS NOT NULL
        GROUP BY EXTRACT(YEAR FROM c.charter_date)
        HAVING COUNT(CASE WHEN cc.charge_type LIKE '%beverage%' OR 
                              cc.charge_type LIKE '%alcohol%' OR
                              cc.charge_type LIKE '%bar%' OR
                              cc.description LIKE '%beverage%' OR
                              cc.description LIKE '%alcohol%' OR
                              cc.description LIKE '%bar%' OR
                              cc.description LIKE '%wine%' OR
                              cc.description LIKE '%champagne%' THEN 1 END) > 0 OR
               COUNT(CASE WHEN c.beverage_service_required = true THEN 1 END) > 0
        ORDER BY year
    """)
    
    beverage_charges = cur.fetchall()
    
    total_beverage_revenue = 0
    
    for year, charges, revenue, beverage_charters, total_charters in beverage_charges:
        year = int(year) if year else 0
        total_beverage_revenue += (revenue or 0)
        
        print(f"   {year}: {charges} beverage charges, ${revenue:,.2f} revenue")
        print(f"        {beverage_charters} charters with beverage service")
        print(f"        {beverage_charters/total_charters*100:.1f}% of charters had beverages")
        print()
    
    # Alternative: Look for beverage patterns in charter rates/charges
    print(f"\n🍾 ADDITIONAL BEVERAGE REVENUE ANALYSIS:")
    print("-" * 42)
    
    # Check for beverage service flag and estimated revenue
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM charter_date) as year,
            COUNT(CASE WHEN beverage_service_required = true THEN 1 END) as beverage_service_charters,
            COUNT(*) as total_charters,
            AVG(CASE WHEN beverage_service_required = true THEN rate END) as avg_rate_with_beverages,
            AVG(CASE WHEN beverage_service_required = false OR beverage_service_required IS NULL THEN rate END) as avg_rate_without_beverages
        FROM charters
        WHERE charter_date IS NOT NULL
        AND rate > 0
        GROUP BY EXTRACT(YEAR FROM charter_date)
        HAVING COUNT(CASE WHEN beverage_service_required = true THEN 1 END) > 0
        ORDER BY year
    """)
    
    beverage_service_analysis = cur.fetchall()
    
    estimated_beverage_premium = 0
    
    for year, bev_charters, total, avg_with_bev, avg_without_bev in beverage_service_analysis:
        year = int(year) if year else 0
        
        if avg_with_bev and avg_without_bev:
            premium = avg_with_bev - avg_without_bev
            total_premium = premium * bev_charters
            estimated_beverage_premium += total_premium
            
            print(f"   {year}: {bev_charters} charters with beverage service")
            print(f"        Avg rate with beverages: ${avg_with_bev:.2f}")
            print(f"        Avg rate without beverages: ${avg_without_bev:.2f}")
            print(f"        Premium per charter: ${premium:.2f}")
            print(f"        Total estimated beverage premium: ${total_premium:,.2f}")
        else:
            print(f"   {year}: {bev_charters} charters with beverage service")
        print()
    
    # Look for specific beverage line items in receipts (detailed analysis)
    print(f"\n🔍 DETAILED ALCOHOL PURCHASE ANALYSIS:")
    print("-" * 40)
    
    cur.execute("""
        SELECT 
            vendor_name,
            COUNT(*) as purchases,
            SUM(gross_amount) as total_spent,
            AVG(gross_amount) as avg_purchase,
            MIN(receipt_date) as first_purchase,
            MAX(receipt_date) as last_purchase
        FROM receipts
        WHERE (
            LOWER(vendor_name) LIKE '%liquor%' OR
            LOWER(vendor_name) LIKE '%wine%' OR
            LOWER(vendor_name) LIKE '%beer%' OR
            LOWER(vendor_name) LIKE '%alcohol%' OR
            LOWER(description) LIKE '%alcohol%' OR
            LOWER(description) LIKE '%wine%' OR
            LOWER(description) LIKE '%beer%' OR
            LOWER(description) LIKE '%liquor%'
        )
        AND gross_amount > 0
        GROUP BY vendor_name
        ORDER BY total_spent DESC
    """)
    
    vendor_analysis = cur.fetchall()
    
    print("   TOP ALCOHOL VENDORS:")
    for vendor, purchases, total, avg, first, last in vendor_analysis[:10]:
        print(f"      {vendor}: {purchases} purchases, ${total:,.2f}")
        print(f"         Average: ${avg:.2f}, Period: {first} to {last}")
        print()
    
    # Summary and profit analysis
    print(f"\n📊 BEVERAGE BUSINESS SUMMARY:")
    print("-" * 30)
    
    print(f"   Total Alcohol Purchases: ${total_alcohol_cost:,.2f}")
    if beverage_charges:
        direct_beverage_revenue = sum(row[2] or 0 for row in beverage_charges)
        print(f"   Direct Beverage Revenue: ${direct_beverage_revenue:,.2f}")
        
        if total_alcohol_cost > 0 and direct_beverage_revenue > 0:
            profit_margin = ((direct_beverage_revenue - total_alcohol_cost) / direct_beverage_revenue) * 100
            print(f"   Direct Profit Margin: {profit_margin:.1f}%")
            print(f"   Direct Profit: ${direct_beverage_revenue - total_alcohol_cost:,.2f}")
    
    if estimated_beverage_premium > 0:
        print(f"   Estimated Premium Revenue: ${estimated_beverage_premium:,.2f}")
        total_estimated_revenue = (direct_beverage_revenue if 'direct_beverage_revenue' in locals() else 0) + estimated_beverage_premium
        
        if total_alcohol_cost > 0:
            total_margin = ((total_estimated_revenue - total_alcohol_cost) / total_estimated_revenue) * 100
            print(f"   Total Estimated Profit Margin: {total_margin:.1f}%")
            print(f"   Total Estimated Profit: ${total_estimated_revenue - total_alcohol_cost:,.2f}")
    
    # Year-over-year comparison
    print(f"\n📈 YEAR-OVER-YEAR PROFIT ANALYSIS:")
    print("-" * 35)
    
    # Create a comprehensive year-by-year comparison
    alcohol_by_year = {int(row[0]): row[2] for row in alcohol_purchases}
    revenue_by_year = {int(row[0]): row[2] for row in beverage_charges}
    
    all_years = sorted(set(list(alcohol_by_year.keys()) + list(revenue_by_year.keys())))
    
    for year in all_years:
        alcohol_cost = alcohol_by_year.get(year, 0)
        beverage_rev = revenue_by_year.get(year, 0)
        
        if alcohol_cost > 0 or beverage_rev > 0:
            print(f"   {year}:")
            print(f"      Alcohol Purchases: ${alcohol_cost:,.2f}")
            print(f"      Beverage Revenue: ${beverage_rev:,.2f}")
            
            if alcohol_cost > 0 and beverage_rev > 0:
                profit = beverage_rev - alcohol_cost
                margin = (profit / beverage_rev) * 100 if beverage_rev > 0 else 0
                print(f"      Profit: ${profit:,.2f} ({margin:.1f}% margin)")
            print()
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    # Set database environment variables
    os.environ['DB_HOST'] = 'localhost'
    os.environ['DB_NAME'] = 'almsdata'
    os.environ['DB_USER'] = 'postgres'
    os.environ['DB_PASSWORD'] = '***REDACTED***'
    
    analyze_alcohol_vs_beverage_revenue()