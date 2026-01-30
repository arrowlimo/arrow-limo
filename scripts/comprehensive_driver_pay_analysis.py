#!/usr/bin/env python3
"""
COMPREHENSIVE DRIVER PAY ANALYSIS
=================================

Calculate average driver pay per hour including:
- Base pay (gross_pay)
- Gratuity/tips
- Vacation pay
- All other compensation components
- Hours worked analysis
- Pay rate trends over time

This provides complete driver compensation visibility.
"""

import os
import psycopg2
from datetime import datetime
import statistics

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

def analyze_driver_pay_comprehensive():
    """Comprehensive analysis of driver pay including all compensation components."""
    
    print("🚗 COMPREHENSIVE DRIVER PAY ANALYSIS")
    print("=" * 50)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # First, check what payroll data we have
    cur.execute("""
        SELECT 
            COUNT(*) as total_records,
            MIN(pay_date) as earliest_date,
            MAX(pay_date) as latest_date,
            COUNT(DISTINCT employee_id) as unique_employees,
            SUM(CASE WHEN gross_pay > 0 THEN 1 ELSE 0 END) as records_with_pay
        FROM driver_payroll
    """)
    
    payroll_summary = cur.fetchone()
    total_records, earliest_date, latest_date, unique_employees, records_with_pay = payroll_summary
    
    print(f"\n📊 PAYROLL DATA OVERVIEW:")
    print(f"   Total Records: {total_records:,}")
    print(f"   Date Range: {earliest_date} to {latest_date}")
    print(f"   Unique Employees: {unique_employees}")
    print(f"   Records with Pay: {records_with_pay:,}")
    
    # Analyze all compensation components
    cur.execute("""
        SELECT 
            AVG(CASE WHEN gross_pay > 0 THEN gross_pay ELSE NULL END) as avg_gross_pay,
            AVG(CASE WHEN net_pay > 0 THEN net_pay ELSE NULL END) as avg_net_pay,
            AVG(CASE WHEN expenses > 0 THEN expenses ELSE NULL END) as avg_expenses,
            AVG(CASE WHEN vacation_pay > 0 THEN vacation_pay ELSE NULL END) as avg_vacation_pay,
            AVG(CASE WHEN wcb_payment > 0 THEN wcb_payment ELSE NULL END) as avg_wcb_payment,
            SUM(CASE WHEN gross_pay > 0 THEN gross_pay ELSE 0 END) as total_gross_pay,
            SUM(CASE WHEN net_pay > 0 THEN net_pay ELSE 0 END) as total_net_pay,
            SUM(CASE WHEN vacation_pay > 0 THEN vacation_pay ELSE 0 END) as total_vacation_pay,
            SUM(CASE WHEN expenses > 0 THEN expenses ELSE 0 END) as total_expenses,
            COUNT(CASE WHEN gross_pay > 0 THEN 1 END) as pay_records
        FROM driver_payroll
        WHERE gross_pay > 0
    """)
    
    pay_analysis = cur.fetchone()
    avg_gross, avg_net, avg_expenses, avg_vacation, avg_wcb, total_gross, total_net, total_vacation, total_expenses, pay_records = pay_analysis
    
    print(f"\n💰 COMPENSATION ANALYSIS:")
    print(f"   Average Gross Pay per Record: ${avg_gross:,.2f}" if avg_gross else "   Average Gross Pay: No data")
    print(f"   Average Net Pay per Record: ${avg_net:,.2f}" if avg_net else "   Average Net Pay: No data")
    print(f"   Average Vacation Pay per Record: ${avg_vacation:,.2f}" if avg_vacation else "   Average Vacation Pay: No data")
    print(f"   Average Expenses per Record: ${avg_expenses:,.2f}" if avg_expenses else "   Average Expenses: No data")
    print(f"   Average WCB Payment per Record: ${avg_wcb:,.2f}" if avg_wcb else "   Average WCB: No data")
    
    print(f"\n📈 TOTAL COMPENSATION:")
    print(f"   Total Gross Pay: ${total_gross:,.2f}")
    print(f"   Total Net Pay: ${total_net:,.2f}")
    print(f"   Total Vacation Pay: ${total_vacation:,.2f}")
    print(f"   Total Expenses: ${total_expenses:,.2f}")
    print(f"   Pay Records: {pay_records:,}")
    
    # Now let's look at charter-based pay analysis
    print(f"\n🚗 CHARTER-BASED PAY ANALYSIS:")
    print("-" * 35)
    
    # Check if we have charter hours data
    cur.execute("""
        SELECT 
            COUNT(*) as charter_count,
            AVG(CASE WHEN calculated_hours > 0 THEN calculated_hours ELSE NULL END) as avg_hours,
            AVG(CASE WHEN driver_hourly_rate > 0 THEN driver_hourly_rate ELSE NULL END) as avg_hourly_rate,
            AVG(CASE WHEN driver_hours_worked > 0 THEN driver_hours_worked ELSE NULL END) as avg_hours_worked,
            AVG(CASE WHEN driver_base_pay > 0 THEN driver_base_pay ELSE NULL END) as avg_base_pay,
            AVG(CASE WHEN driver_gratuity > 0 THEN driver_gratuity ELSE NULL END) as avg_gratuity,
            AVG(CASE WHEN driver_total_expense > 0 THEN driver_total_expense ELSE NULL END) as avg_total_expense,
            SUM(CASE WHEN driver_gratuity > 0 THEN driver_gratuity ELSE 0 END) as total_gratuity,
            COUNT(CASE WHEN driver_gratuity > 0 THEN 1 END) as gratuity_records
        FROM charters
        WHERE assigned_driver_id IS NOT NULL
    """)
    
    charter_analysis = cur.fetchone()
    charter_count, avg_charter_hours, avg_charter_rate, avg_hours_worked, avg_base_pay, avg_gratuity, avg_total_expense, total_gratuity, gratuity_records = charter_analysis
    
    print(f"   Charter Records with Drivers: {charter_count:,}")
    if avg_charter_hours:
        print(f"   Average Charter Hours: {avg_charter_hours:.2f}")
    if avg_charter_rate:
        print(f"   Average Hourly Rate: ${avg_charter_rate:.2f}")
    if avg_hours_worked:
        print(f"   Average Hours Worked: {avg_hours_worked:.2f}")
    if avg_base_pay:
        print(f"   Average Base Pay per Charter: ${avg_base_pay:.2f}")
    if avg_gratuity:
        print(f"   Average Gratuity per Charter: ${avg_gratuity:.2f}")
    if total_gratuity > 0:
        print(f"   Total Gratuity Paid: ${total_gratuity:,.2f}")
        print(f"   Gratuity Records: {gratuity_records:,}")
    
    # Hourly rate calculation attempts
    print(f"\n⏰ HOURLY RATE CALCULATIONS:")
    print("-" * 30)
    
    # Method 1: From payroll data (if we have hours)
    cur.execute("""
        SELECT 
            year, month,
            SUM(gross_pay) as total_pay,
            AVG(gross_pay) as avg_pay,
            COUNT(*) as records
        FROM driver_payroll
        WHERE gross_pay > 0
        GROUP BY year, month
        ORDER BY year DESC, month DESC
        LIMIT 12
    """)
    
    monthly_analysis = cur.fetchall()
    
    if monthly_analysis:
        print(f"   📅 RECENT MONTHLY PAY ANALYSIS (Last 12 months):")
        for year, month, total_pay, avg_pay, records in monthly_analysis:
            print(f"      {year}-{month:02d}: Total: ${total_pay:,.2f}, Avg: ${avg_pay:,.2f}, Records: {records}")
    
    # Method 2: Charter hours vs payment analysis
    cur.execute("""
        SELECT 
            c.assigned_driver_id,
            e.full_name,
            COUNT(c.charter_id) as charter_count,
            SUM(CASE WHEN c.calculated_hours > 0 THEN c.calculated_hours ELSE 0 END) as total_charter_hours,
            SUM(CASE WHEN c.driver_base_pay > 0 THEN c.driver_base_pay ELSE 0 END) as total_charter_pay,
            SUM(CASE WHEN c.driver_gratuity > 0 THEN c.driver_gratuity ELSE 0 END) as total_gratuity,
            AVG(CASE WHEN c.driver_hourly_rate > 0 THEN c.driver_hourly_rate ELSE NULL END) as avg_hourly_rate
        FROM charters c
        LEFT JOIN employees e ON c.assigned_driver_id = e.employee_id
        WHERE c.assigned_driver_id IS NOT NULL
        GROUP BY c.assigned_driver_id, e.full_name
        HAVING COUNT(c.charter_id) > 5  -- Only drivers with multiple charters
        ORDER BY total_charter_pay DESC
        LIMIT 10
    """)
    
    driver_analysis = cur.fetchall()
    
    if driver_analysis:
        print(f"\n👥 TOP DRIVERS BY CHARTER PAY:")
        print("-" * 40)
        total_estimated_hourly_rates = []
        
        for driver_id, name, charters, total_hours, total_pay, gratuity, avg_rate in driver_analysis:
            total_compensation = (total_pay or 0) + (gratuity or 0)
            
            if total_hours and total_hours > 0 and total_compensation > 0:
                estimated_hourly = total_compensation / total_hours
                total_estimated_hourly_rates.append(estimated_hourly)
                
                print(f"   {name or 'Unknown'} (ID: {driver_id}):")
                print(f"      Charters: {charters}, Hours: {total_hours:.1f}")
                print(f"      Base Pay: ${total_pay:,.2f}, Gratuity: ${gratuity:,.2f}")
                print(f"      Total Compensation: ${total_compensation:,.2f}")
                print(f"      Estimated Hourly Rate: ${estimated_hourly:.2f}/hour")
                if avg_rate:
                    print(f"      Recorded Hourly Rate: ${avg_rate:.2f}/hour")
                print()
        
        if total_estimated_hourly_rates:
            avg_hourly_all = statistics.mean(total_estimated_hourly_rates)
            median_hourly = statistics.median(total_estimated_hourly_rates)
            print(f"🎯 OVERALL HOURLY RATE ESTIMATES:")
            print(f"   Average Hourly Rate: ${avg_hourly_all:.2f}/hour")
            print(f"   Median Hourly Rate: ${median_hourly:.2f}/hour")
            print(f"   Range: ${min(total_estimated_hourly_rates):.2f} - ${max(total_estimated_hourly_rates):.2f}/hour")
    
    # Employee records analysis
    cur.execute("""
        SELECT 
            COUNT(*) as total_employees,
            COUNT(CASE WHEN is_chauffeur = true THEN 1 END) as chauffeurs,
            AVG(CASE WHEN hourly_rate > 0 THEN hourly_rate ELSE NULL END) as avg_recorded_rate,
            AVG(CASE WHEN salary > 0 THEN salary ELSE NULL END) as avg_salary
        FROM employees
        WHERE status = 'active' OR status IS NULL
    """)
    
    employee_analysis = cur.fetchone()
    total_employees, chauffeurs, avg_recorded_rate, avg_salary = employee_analysis
    
    print(f"\n👔 EMPLOYEE RECORDS ANALYSIS:")
    print(f"   Total Active Employees: {total_employees}")
    print(f"   Chauffeurs: {chauffeurs}")
    if avg_recorded_rate:
        print(f"   Average Recorded Hourly Rate: ${avg_recorded_rate:.2f}/hour")
    if avg_salary:
        print(f"   Average Salary: ${avg_salary:,.2f}")
    
    # Final summary calculation
    print(f"\n🎯 COMPREHENSIVE PAY SUMMARY:")
    print("=" * 35)
    
    # Calculate total compensation per hour if possible
    if total_estimated_hourly_rates:
        print(f"   DRIVER HOURLY COMPENSATION (Including all pay + gratuity):")
        print(f"   • Average: ${statistics.mean(total_estimated_hourly_rates):.2f}/hour")
        print(f"   • Median: ${statistics.median(total_estimated_hourly_rates):.2f}/hour")
        print(f"   • Based on: Charter hours vs total compensation")
        print()
    
    if avg_recorded_rate:
        print(f"   RECORDED BASE RATES:")
        print(f"   • Average Employee Hourly Rate: ${avg_recorded_rate:.2f}/hour")
        print(f"   • Based on: Employee records")
        print()
    
    # Total compensation summary
    total_all_compensation = total_gross + total_vacation + total_expenses + total_gratuity
    print(f"   TOTAL COMPENSATION PAID:")
    print(f"   • Gross Pay: ${total_gross:,.2f}")
    print(f"   • Vacation Pay: ${total_vacation:,.2f}")
    print(f"   • Gratuity: ${total_gratuity:,.2f}")
    print(f"   • Expenses: ${total_expenses:,.2f}")
    print(f"   • TOTAL: ${total_all_compensation:,.2f}")
    
    if pay_records > 0:
        avg_total_per_record = total_all_compensation / pay_records
        print(f"   • Average per Pay Record: ${avg_total_per_record:,.2f}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    # Set database environment variables
    os.environ['DB_HOST'] = 'localhost'
    os.environ['DB_NAME'] = 'almsdata'
    os.environ['DB_USER'] = 'postgres'
    os.environ['DB_PASSWORD'] = '***REDACTED***'
    
    analyze_driver_pay_comprehensive()