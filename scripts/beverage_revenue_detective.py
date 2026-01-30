#!/usr/bin/env python3
"""
COMPREHENSIVE BEVERAGE REVENUE DETECTIVE WORK
=============================================

Since direct beverage charges aren't showing up, let's investigate:
1. Charter rates with beverage service flags
2. Special event pricing patterns
3. Charter notes mentioning beverages
4. Rate premiums that might include beverages
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

def find_beverage_revenue():
    """Detective work to find beverage revenue in the system."""
    
    print("🕵️ BEVERAGE REVENUE DETECTIVE ANALYSIS")
    print("=" * 45)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # First, let's see what charter_charges table structure looks like
    print("\n🔍 CHARTER CHARGES TABLE ANALYSIS:")
    print("-" * 35)
    
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'charter_charges'
        ORDER BY ordinal_position
    """)
    
    cc_columns = cur.fetchall()
    print("   Charter Charges Table Columns:")
    for col, dtype in cc_columns:
        print(f"      {col}: {dtype}")
    
    # Check if charter_charges table exists and has data
    cur.execute("""
        SELECT COUNT(*) FROM charter_charges
    """)
    
    cc_count = cur.fetchone()[0]
    print(f"\n   Total Charter Charges Records: {cc_count:,}")
    
    if cc_count > 0:
        # Sample some charter charges to see what they look like
        cur.execute("""
            SELECT charge_type, description, amount, COUNT(*)
            FROM charter_charges
            GROUP BY charge_type, description, amount
            ORDER BY COUNT(*) DESC
            LIMIT 20
        """)
        
        sample_charges = cur.fetchall()
        print("\n   Sample Charter Charges:")
        for charge_type, desc, amount, count in sample_charges:
            print(f"      {charge_type or 'NULL'} | {desc or 'NULL'} | ${amount or 0:.2f} | {count} times")
    
    # Look for beverage service flags in charters
    print(f"\n🥂 BEVERAGE SERVICE FLAGS ANALYSIS:")
    print("-" * 38)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM charter_date) as year,
            COUNT(CASE WHEN beverage_service_required = true THEN 1 END) as with_beverages,
            COUNT(*) as total_charters,
            AVG(CASE WHEN beverage_service_required = true THEN rate END) as avg_rate_with_bev,
            AVG(CASE WHEN beverage_service_required = false OR beverage_service_required IS NULL THEN rate END) as avg_rate_without_bev,
            SUM(CASE WHEN beverage_service_required = true THEN rate END) as total_revenue_with_bev
        FROM charters
        WHERE charter_date IS NOT NULL AND rate > 0
        GROUP BY EXTRACT(YEAR FROM charter_date)
        HAVING COUNT(CASE WHEN beverage_service_required = true THEN 1 END) > 0
        ORDER BY year
    """)
    
    beverage_flags = cur.fetchall()
    
    total_beverage_revenue_estimated = 0
    
    for year, with_bev, total, avg_with, avg_without, total_rev in beverage_flags:
        year = int(year) if year else 0
        total_beverage_revenue_estimated += (total_rev or 0)
        
        premium = (avg_with or 0) - (avg_without or 0) if avg_with and avg_without else 0
        estimated_beverage_premium = premium * with_bev if premium > 0 else 0
        
        print(f"   {year}: {with_bev} charters with beverage service ({with_bev/total*100:.1f}%)")
        print(f"        Total revenue with beverages: ${total_rev or 0:,.2f}")
        if avg_with and avg_without:
            print(f"        Rate premium: ${premium:.2f} per charter (${estimated_beverage_premium:,.2f} total)")
        print()
    
    # Look for beverage mentions in charter notes
    print(f"\n📝 BEVERAGE MENTIONS IN CHARTER NOTES:")
    print("-" * 40)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM charter_date) as year,
            COUNT(*) as charters_with_beverage_notes,
            SUM(rate) as total_revenue_with_beverage_notes,
            AVG(rate) as avg_rate_with_beverage_notes,
            STRING_AGG(DISTINCT SUBSTRING(notes, 1, 50), ' | ') as sample_notes
        FROM charters
        WHERE (
            LOWER(notes) LIKE '%alcohol%' OR
            LOWER(notes) LIKE '%wine%' OR
            LOWER(notes) LIKE '%beer%' OR
            LOWER(notes) LIKE '%champagne%' OR
            LOWER(notes) LIKE '%beverage%' OR
            LOWER(notes) LIKE '%bar%' OR
            LOWER(notes) LIKE '%drink%' OR
            LOWER(booking_notes) LIKE '%alcohol%' OR
            LOWER(booking_notes) LIKE '%wine%' OR
            LOWER(booking_notes) LIKE '%beverage%' OR
            LOWER(booking_notes) LIKE '%bar%'
        )
        AND charter_date IS NOT NULL
        AND rate > 0
        GROUP BY EXTRACT(YEAR FROM charter_date)
        ORDER BY year
    """)
    
    beverage_notes = cur.fetchall()
    
    for year, count, revenue, avg_rate, notes in beverage_notes:
        year = int(year) if year else 0
        print(f"   {year}: {count} charters mention beverages, ${revenue:,.2f} revenue")
        print(f"        Average rate: ${avg_rate:.2f}")
        print(f"        Sample notes: {notes[:100]}...")
        print()
    
    # Look for high-value charters that might include beverages
    print(f"\n💰 HIGH-VALUE CHARTERS (Potential Beverage Service):")
    print("-" * 52)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM charter_date) as year,
            COUNT(CASE WHEN rate >= 1000 THEN 1 END) as high_value_charters,
            SUM(CASE WHEN rate >= 1000 THEN rate END) as high_value_revenue,
            AVG(CASE WHEN rate >= 1000 THEN rate END) as avg_high_value_rate,
            COUNT(*) as total_charters,
            AVG(rate) as overall_avg_rate
        FROM charters
        WHERE charter_date IS NOT NULL AND rate > 0
        GROUP BY EXTRACT(YEAR FROM charter_date)
        HAVING COUNT(CASE WHEN rate >= 1000 THEN 1 END) > 0
        ORDER BY year
    """)
    
    high_value = cur.fetchall()
    
    for year, hv_count, hv_revenue, hv_avg, total, overall_avg in high_value:
        year = int(year) if year else 0
        premium_potential = (hv_avg - overall_avg) * hv_count if hv_avg and overall_avg else 0
        
        print(f"   {year}: {hv_count} high-value charters (${hv_revenue:,.2f})")
        print(f"        Average high-value rate: ${hv_avg:.2f} vs overall ${overall_avg:.2f}")
        print(f"        Potential beverage premium: ${premium_potential:,.2f}")
        print()
    
    # Look at payment patterns that might indicate beverage charges
    print(f"\n💳 PAYMENT ANALYSIS FOR BEVERAGE INDICATORS:")
    print("-" * 45)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM payment_date) as year,
            COUNT(CASE WHEN notes LIKE '%beverage%' OR notes LIKE '%alcohol%' OR notes LIKE '%bar%' THEN 1 END) as beverage_payments,
            SUM(CASE WHEN notes LIKE '%beverage%' OR notes LIKE '%alcohol%' OR notes LIKE '%bar%' THEN amount END) as beverage_payment_amount
        FROM payments
        WHERE payment_date IS NOT NULL
        GROUP BY EXTRACT(YEAR FROM payment_date)
        HAVING COUNT(CASE WHEN notes LIKE '%beverage%' OR notes LIKE '%alcohol%' OR notes LIKE '%bar%' THEN 1 END) > 0
        ORDER BY year
    """)
    
    beverage_payments = cur.fetchall()
    
    for year, count, amount in beverage_payments:
        year = int(year) if year else 0
        print(f"   {year}: {count} payments mention beverages, ${amount or 0:,.2f}")
    
    # FINAL SUMMARY - Calculate estimated beverage business
    print(f"\n📊 ESTIMATED BEVERAGE BUSINESS SUMMARY:")
    print("-" * 40)
    
    # Alcohol purchases from earlier analysis
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            SUM(gross_amount) as alcohol_cost
        FROM receipts
        WHERE (
            LOWER(vendor_name) LIKE '%liquor%' OR
            LOWER(vendor_name) LIKE '%wine%' OR
            LOWER(vendor_name) LIKE '%beer%' OR
            LOWER(description) LIKE '%alcohol%' OR
            LOWER(description) LIKE '%wine%' OR
            LOWER(description) LIKE '%liquor%'
        )
        AND receipt_date IS NOT NULL
        AND gross_amount > 0
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    
    alcohol_costs = {int(row[0]): row[1] for row in cur.fetchall()}
    
    # Create year-by-year analysis with estimated revenue
    beverage_service_revenue = {}
    for year, with_bev, total, avg_with, avg_without, total_rev in beverage_flags:
        year = int(year) if year else 0
        beverage_service_revenue[year] = total_rev or 0
    
    print("   YEAR-BY-YEAR BEVERAGE BUSINESS ANALYSIS:")
    print()
    
    total_alcohol_investment = sum(alcohol_costs.values())
    total_estimated_revenue = sum(beverage_service_revenue.values())
    
    all_years = sorted(set(list(alcohol_costs.keys()) + list(beverage_service_revenue.keys())))
    
    for year in all_years:
        alcohol_cost = alcohol_costs.get(year, 0)
        beverage_rev = beverage_service_revenue.get(year, 0)
        
        if alcohol_cost > 0 or beverage_rev > 0:
            print(f"   {year}:")
            print(f"      Alcohol Investment: ${alcohol_cost:,.2f}")
            print(f"      Est. Beverage Revenue: ${beverage_rev:,.2f}")
            
            if alcohol_cost > 0 and beverage_rev > 0:
                roi = (beverage_rev / alcohol_cost) * 100
                profit = beverage_rev - alcohol_cost
                print(f"      ROI: {roi:.1f}% (${profit:,.2f} profit)")
            print()
    
    print(f"\n🎯 BUSINESS TOTALS:")
    print(f"   Total Alcohol Investment: ${total_alcohol_investment:,.2f}")
    print(f"   Total Estimated Revenue: ${total_estimated_revenue:,.2f}")
    
    if total_alcohol_investment > 0 and total_estimated_revenue > 0:
        total_roi = (total_estimated_revenue / total_alcohol_investment) * 100
        total_profit = total_estimated_revenue - total_alcohol_investment
        print(f"   Overall ROI: {total_roi:.1f}%")
        print(f"   Total Estimated Profit: ${total_profit:,.2f}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    # Set database environment variables
    os.environ['DB_HOST'] = 'localhost'
    os.environ['DB_NAME'] = 'almsdata'
    os.environ['DB_USER'] = 'postgres'
    os.environ['DB_PASSWORD'] = '***REDACTED***'
    
    find_beverage_revenue()