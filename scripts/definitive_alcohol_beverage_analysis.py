#!/usr/bin/env python3
"""
DEFINITIVE ALCOHOL vs BEVERAGE REVENUE ANALYSIS
===============================================

Based on detective work, the beverage revenue is embedded in charter rates
rather than tracked as separate charges. This analysis calculates the
true alcohol business profitability.
"""

import os
import psycopg2
from datetime import datetime

# Database connection
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'almsdata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '***REMOVED***')

def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def calculate_alcohol_beverage_business():
    """Calculate the complete alcohol vs beverage revenue story."""
    
    print("🍷 DEFINITIVE ALCOHOL vs BEVERAGE BUSINESS ANALYSIS")
    print("=" * 60)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get alcohol purchases by year
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as purchases,
            SUM(gross_amount) as total_cost,
            SUM(gst_amount) as gst_paid,
            AVG(gross_amount) as avg_purchase
        FROM receipts
        WHERE (
            LOWER(vendor_name) LIKE '%liquor%' OR
            LOWER(vendor_name) LIKE '%wine%' OR
            LOWER(vendor_name) LIKE '%beer%' OR
            LOWER(vendor_name) LIKE '%alcohol%' OR
            LOWER(description) LIKE '%alcohol%' OR
            LOWER(description) LIKE '%wine%' OR
            LOWER(description) LIKE '%beer%' OR
            LOWER(description) LIKE '%liquor%' OR
            LOWER(description) LIKE '%champagne%'
        )
        AND receipt_date IS NOT NULL
        AND gross_amount > 0
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    
    alcohol_data = cur.fetchall()
    
    # Get high-value charters that likely include beverages
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM charter_date) as year,
            COUNT(CASE WHEN rate >= 1000 THEN 1 END) as premium_charters,
            SUM(CASE WHEN rate >= 1000 THEN rate END) as premium_revenue,
            AVG(CASE WHEN rate >= 1000 THEN rate END) as avg_premium_rate,
            COUNT(*) as total_charters,
            AVG(rate) as avg_standard_rate
        FROM charters
        WHERE charter_date IS NOT NULL AND rate > 0
        GROUP BY EXTRACT(YEAR FROM charter_date)
        ORDER BY year
    """)
    
    charter_data = cur.fetchall()
    
    # Get charters with explicit beverage mentions
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM charter_date) as year,
            COUNT(*) as beverage_mention_charters,
            SUM(rate) as explicit_beverage_revenue,
            STRING_AGG(DISTINCT 
                CASE 
                    WHEN LOWER(notes) LIKE '%champagne%' THEN 'champagne'
                    WHEN LOWER(notes) LIKE '%wine%' THEN 'wine'
                    WHEN LOWER(notes) LIKE '%beer%' THEN 'beer'
                    WHEN LOWER(notes) LIKE '%alcohol%' THEN 'alcohol'
                    ELSE 'beverages'
                END, ', ') as beverage_types
        FROM charters
        WHERE (
            LOWER(notes) LIKE '%alcohol%' OR
            LOWER(notes) LIKE '%wine%' OR
            LOWER(notes) LIKE '%beer%' OR
            LOWER(notes) LIKE '%champagne%' OR
            LOWER(notes) LIKE '%beverage%' OR
            LOWER(booking_notes) LIKE '%alcohol%' OR
            LOWER(booking_notes) LIKE '%wine%' OR
            LOWER(booking_notes) LIKE '%beverage%'
        )
        AND charter_date IS NOT NULL
        AND rate > 0
        GROUP BY EXTRACT(YEAR FROM charter_date)
        ORDER BY year
    """)
    
    explicit_beverage_data = cur.fetchall()
    
    # Create comprehensive year-by-year analysis
    print("\n📊 YEAR-BY-YEAR ALCOHOL BUSINESS ANALYSIS:")
    print("-" * 45)
    
    # Organize data by year
    alcohol_by_year = {int(row[0]): row for row in alcohol_data}
    charter_by_year = {int(row[0]): row for row in charter_data}
    explicit_by_year = {int(row[0]): row for row in explicit_beverage_data}
    
    all_years = sorted(set(list(alcohol_by_year.keys()) + list(charter_by_year.keys())))
    
    total_alcohol_investment = 0
    total_premium_revenue = 0
    total_explicit_beverage_revenue = 0
    total_estimated_beverage_premium = 0
    
    for year in all_years:
        print(f"\n🗓️  {year}:")
        print("-" * 15)
        
        # Alcohol purchases
        if year in alcohol_by_year:
            year_data, purchases, cost, gst, avg_purchase = alcohol_by_year[year]
            cost = float(cost)
            gst = float(gst)
            avg_purchase = float(avg_purchase)
            total_alcohol_investment += cost
            
            print(f"   💰 ALCOHOL INVESTMENT:")
            print(f"      Purchases: {purchases}")
            print(f"      Total Cost: ${cost:,.2f}")
            print(f"      GST Paid: ${gst:,.2f}")
            print(f"      Average Purchase: ${avg_purchase:.2f}")
        else:
            cost = 0
            print(f"   💰 ALCOHOL INVESTMENT: $0.00")
        
        # Charter revenue analysis
        if year in charter_by_year:
            year_data, premium_count, premium_rev, avg_premium, total_charters, avg_standard = charter_by_year[year]
            premium_rev = float(premium_rev or 0)
            total_premium_revenue += premium_rev
            
            # Estimate beverage premium (difference between premium and standard rates)
            if avg_premium and avg_standard and premium_count:
                rate_premium = float(avg_premium) - float(avg_standard)
                estimated_beverage_premium = rate_premium * premium_count * 0.3  # Assume 30% of premium is beverages
                total_estimated_beverage_premium += estimated_beverage_premium
            else:
                estimated_beverage_premium = 0
            
            print(f"   🥂 BEVERAGE REVENUE (ESTIMATED):")
            print(f"      Premium Charters: {premium_count or 0}")
            print(f"      Premium Revenue: ${premium_rev or 0:,.2f}")
            print(f"      Avg Premium Rate: ${avg_premium or 0:.2f}")
            print(f"      Est. Beverage Premium: ${estimated_beverage_premium:,.2f}")
        else:
            estimated_beverage_premium = 0
            print(f"   🥂 BEVERAGE REVENUE: $0.00")
        
        # Explicit beverage mentions
        if year in explicit_by_year:
            year_data, bev_charters, explicit_rev, bev_types = explicit_by_year[year]
            explicit_rev = float(explicit_rev)
            total_explicit_beverage_revenue += explicit_rev
            
            print(f"   📝 EXPLICIT BEVERAGE CHARTERS:")
            print(f"      Charters: {bev_charters}")
            print(f"      Revenue: ${explicit_rev:,.2f}")
            print(f"      Types: {bev_types}")
        
        # Calculate year profitability
        explicit_revenue = float(explicit_by_year.get(year, (0, 0, 0, ''))[2]) if year in explicit_by_year else 0
        total_beverage_revenue = estimated_beverage_premium + explicit_revenue
        
        if cost > 0 and total_beverage_revenue > 0:
            profit = total_beverage_revenue - cost
            roi = (total_beverage_revenue / cost) * 100
            margin = (profit / total_beverage_revenue) * 100
            
            print(f"   💡 YEAR PROFITABILITY:")
            print(f"      Total Beverage Revenue: ${total_beverage_revenue:,.2f}")
            print(f"      Profit: ${profit:,.2f}")
            print(f"      ROI: {roi:.1f}%")
            print(f"      Margin: {margin:.1f}%")
        elif cost > 0:
            print(f"   [WARN]  COST WITHOUT CLEAR REVENUE: ${cost:,.2f}")
        elif total_beverage_revenue > 0:
            print(f"   [WARN]  REVENUE WITHOUT CLEAR COSTS: ${total_beverage_revenue:,.2f}")
    
    # BUSINESS SUMMARY
    print(f"\n\n🎯 COMPLETE BEVERAGE BUSINESS SUMMARY:")
    print("=" * 45)
    
    print(f"\n💰 TOTAL INVESTMENTS:")
    print(f"   Alcohol Purchases: ${total_alcohol_investment:,.2f}")
    print(f"   Average Annual Investment: ${total_alcohol_investment/len(alcohol_by_year):,.2f}")
    
    print(f"\n🥂 TOTAL REVENUE (ESTIMATED):")
    print(f"   Explicit Beverage Revenue: ${total_explicit_beverage_revenue:,.2f}")
    print(f"   Estimated Premium Revenue: ${total_estimated_beverage_premium:,.2f}")
    
    total_beverage_revenue = total_explicit_beverage_revenue + total_estimated_beverage_premium
    
    print(f"   Total Est. Beverage Revenue: ${total_beverage_revenue:,.2f}")
    
    if total_alcohol_investment > 0 and total_beverage_revenue > 0:
        total_profit = total_beverage_revenue - total_alcohol_investment
        total_roi = (total_beverage_revenue / total_alcohol_investment) * 100
        total_margin = (total_profit / total_beverage_revenue) * 100
        
        print(f"\n📈 OVERALL PROFITABILITY:")
        print(f"   Total Profit: ${total_profit:,.2f}")
        print(f"   Overall ROI: {total_roi:.1f}%")
        print(f"   Profit Margin: {total_margin:.1f}%")
        
        print(f"\n🔍 BUSINESS MODEL INSIGHTS:")
        print(f"   • Beverage service appears integrated into premium charter rates")
        print(f"   • High-value charters (>$1000) likely include beverage service")
        print(f"   • Explicit beverage mentions show luxury service (champagne, wine)")
        print(f"   • ROI of {total_roi:.1f}% suggests profitable beverage operation")
        
        # Peak years analysis
        peak_alcohol_years = sorted(alcohol_by_year.items(), key=lambda x: x[1][2], reverse=True)[:3]
        print(f"\n📊 PEAK ALCOHOL INVESTMENT YEARS:")
        for year, (_, purchases, cost, gst, avg) in peak_alcohol_years:
            print(f"   {year}: ${cost:,.2f} ({purchases} purchases)")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    # Set database environment variables
    os.environ['DB_HOST'] = 'localhost'
    os.environ['DB_NAME'] = 'almsdata'
    os.environ['DB_USER'] = 'postgres'
    os.environ['DB_PASSWORD'] = '***REMOVED***'
    
    calculate_alcohol_beverage_business()