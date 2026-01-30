#!/usr/bin/env python3
"""
DRIVER PAY YEAR ANALYSIS
========================

Detailed breakdown of what years are included in the driver pay analysis
and how much data we have for each year.
"""

import os
import psycopg2
from datetime import datetime

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

def analyze_pay_years():
    """Analyze what years are included in the driver pay analysis."""
    
    print("📅 DRIVER PAY DATA - YEARS INCLUDED ANALYSIS")
    print("=" * 55)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Analyze payroll data by year
    print("\n💰 PAYROLL DATA BY YEAR:")
    print("-" * 30)
    
    cur.execute("""
        SELECT 
            year,
            COUNT(*) as total_records,
            COUNT(CASE WHEN gross_pay > 0 THEN 1 END) as records_with_pay,
            SUM(CASE WHEN gross_pay > 0 THEN gross_pay ELSE 0 END) as total_gross_pay,
            AVG(CASE WHEN gross_pay > 0 THEN gross_pay ELSE NULL END) as avg_gross_pay,
            MIN(pay_date) as earliest_date,
            MAX(pay_date) as latest_date
        FROM driver_payroll
        GROUP BY year
        ORDER BY year
    """)
    
    payroll_years = cur.fetchall()
    
    total_payroll_records = 0
    total_payroll_amount = 0
    
    for year, records, pay_records, total_pay, avg_pay, earliest, latest in payroll_years:
        total_payroll_records += records
        total_payroll_amount += (total_pay or 0)
        
        print(f"   {year}: {records:,} records ({pay_records:,} with pay)")
        if total_pay:
            print(f"        Total Pay: ${total_pay:,.2f}, Avg: ${avg_pay:.2f}")
        if earliest and latest:
            print(f"        Date Range: {earliest} to {latest}")
        print()
    
    print(f"📊 PAYROLL SUMMARY:")
    print(f"   Years Covered: {len(payroll_years)} years")
    print(f"   Total Records: {total_payroll_records:,}")
    print(f"   Total Amount: ${total_payroll_amount:,.2f}")
    
    # Analyze charter data by year
    print(f"\n🚗 CHARTER DATA BY YEAR:")
    print("-" * 25)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM charter_date) as year,
            COUNT(*) as total_charters,
            COUNT(CASE WHEN assigned_driver_id IS NOT NULL THEN 1 END) as charters_with_drivers,
            SUM(CASE WHEN driver_base_pay > 0 THEN driver_base_pay ELSE 0 END) as total_base_pay,
            SUM(CASE WHEN driver_gratuity > 0 THEN driver_gratuity ELSE 0 END) as total_gratuity,
            AVG(CASE WHEN calculated_hours > 0 THEN calculated_hours ELSE NULL END) as avg_hours
        FROM charters
        WHERE charter_date IS NOT NULL
        GROUP BY EXTRACT(YEAR FROM charter_date)
        ORDER BY year
    """)
    
    charter_years = cur.fetchall()
    
    total_charter_records = 0
    total_charter_base_pay = 0
    total_charter_gratuity = 0
    
    for year, charters, with_drivers, base_pay, gratuity, avg_hours in charter_years:
        year = int(year) if year else 0
        total_charter_records += charters
        total_charter_base_pay += (base_pay or 0)
        total_charter_gratuity += (gratuity or 0)
        
        print(f"   {year}: {charters:,} charters ({with_drivers:,} with drivers)")
        if base_pay or gratuity:
            total_comp = (base_pay or 0) + (gratuity or 0)
            print(f"        Base Pay: ${base_pay or 0:,.2f}, Gratuity: ${gratuity or 0:,.2f}")
            print(f"        Total Compensation: ${total_comp:,.2f}")
        if avg_hours:
            print(f"        Avg Hours: {avg_hours:.1f}")
        print()
    
    print(f"📊 CHARTER SUMMARY:")
    print(f"   Years Covered: {len(charter_years)} years")
    print(f"   Total Charters: {total_charter_records:,}")
    print(f"   Total Base Pay: ${total_charter_base_pay:,.2f}")
    print(f"   Total Gratuity: ${total_charter_gratuity:,.2f}")
    print(f"   Combined Charter Pay: ${total_charter_base_pay + total_charter_gratuity:,.2f}")
    
    # Recent activity analysis
    print(f"\n📈 RECENT ACTIVITY ANALYSIS (2020-2025):")
    print("-" * 45)
    
    cur.execute("""
        SELECT 
            year,
            COUNT(*) as payroll_records,
            SUM(CASE WHEN gross_pay > 0 THEN gross_pay ELSE 0 END) as payroll_amount
        FROM driver_payroll
        WHERE year >= 2020
        GROUP BY year
        ORDER BY year DESC
    """)
    
    recent_payroll = cur.fetchall()
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM charter_date) as year,
            COUNT(*) as charter_count,
            SUM(CASE WHEN driver_base_pay > 0 THEN driver_base_pay ELSE 0 END) + 
            SUM(CASE WHEN driver_gratuity > 0 THEN driver_gratuity ELSE 0 END) as charter_compensation
        FROM charters
        WHERE charter_date >= '2020-01-01'
        GROUP BY EXTRACT(YEAR FROM charter_date)
        ORDER BY year DESC
    """)
    
    recent_charters = cur.fetchall()
    
    print("   PAYROLL ACTIVITY:")
    for year, records, amount in recent_payroll:
        print(f"      {year}: {records:,} records, ${amount:,.2f}")
    
    print("\n   CHARTER ACTIVITY:")
    for year, charters, compensation in recent_charters:
        year = int(year) if year else 0
        print(f"      {year}: {charters:,} charters, ${compensation or 0:,.2f}")
    
    # Business period analysis
    print(f"\n🏢 BUSINESS PERIOD ANALYSIS:")
    print("-" * 30)
    
    # Peak years
    cur.execute("""
        SELECT 
            year,
            SUM(CASE WHEN gross_pay > 0 THEN gross_pay ELSE 0 END) as total_pay
        FROM driver_payroll
        WHERE year BETWEEN 2007 AND 2025
        GROUP BY year
        ORDER BY total_pay DESC
        LIMIT 5
    """)
    
    peak_years = cur.fetchall()
    
    print("   TOP 5 PAYROLL YEARS:")
    for year, amount in peak_years:
        print(f"      {year}: ${amount:,.2f}")
    
    # Current year analysis
    current_year = 2025
    cur.execute("""
        SELECT 
            month,
            COUNT(*) as records,
            SUM(CASE WHEN gross_pay > 0 THEN gross_pay ELSE 0 END) as amount
        FROM driver_payroll
        WHERE year = %s
        GROUP BY month
        ORDER BY month DESC
    """, (current_year,))
    
    current_year_data = cur.fetchall()
    
    print(f"\n   2025 MONTHLY BREAKDOWN:")
    for month, records, amount in current_year_data:
        month_name = datetime(2025, month, 1).strftime('%B')
        print(f"      {month_name}: {records} records, ${amount:,.2f}")
    
    # Data quality assessment
    print(f"\n[OK] DATA QUALITY ASSESSMENT:")
    print("-" * 30)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_payroll,
            COUNT(CASE WHEN pay_date IS NOT NULL THEN 1 END) as with_dates,
            COUNT(CASE WHEN gross_pay > 0 THEN 1 END) as with_pay,
            COUNT(CASE WHEN employee_id IS NOT NULL THEN 1 END) as with_employee_id
        FROM driver_payroll
    """)
    
    quality_check = cur.fetchone()
    total, with_dates, with_pay, with_employee = quality_check
    
    print(f"   Total Payroll Records: {total:,}")
    print(f"   Records with Dates: {with_dates:,} ({with_dates/total*100:.1f}%)")
    print(f"   Records with Pay: {with_pay:,} ({with_pay/total*100:.1f}%)")
    print(f"   Records with Employee ID: {with_employee:,} ({with_employee/total*100:.1f}%)")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    # Set database environment variables
    os.environ['DB_HOST'] = 'localhost'
    os.environ['DB_NAME'] = 'almsdata'
    os.environ['DB_USER'] = 'postgres'
    os.environ['DB_PASSWORD'] = '***REDACTED***'
    
    analyze_pay_years()