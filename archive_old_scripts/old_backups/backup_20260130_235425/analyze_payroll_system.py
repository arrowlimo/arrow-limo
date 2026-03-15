#!/usr/bin/env python3
"""
Payroll System Detailed Analysis
Analyze the comprehensive payroll system structure and data flow
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os

def get_db_connection():
    """Get PostgreSQL connection"""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
        cursor_factory=RealDictCursor
    )

def main():
    print("💰 PAYROLL SYSTEM DETAILED ANALYSIS")
    print("=" * 50)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 1. Driver Payroll Table Analysis
        print("📊 DRIVER PAYROLL TABLE ANALYSIS:")
        
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'driver_payroll' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        
        driver_payroll_columns = cur.fetchall()
        print(f"   driver_payroll table has {len(driver_payroll_columns)} columns:")
        for col in driver_payroll_columns:
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            print(f"      {col['column_name']}: {col['data_type']} {nullable}")
        
        # 2. Driver Payroll Data Analysis
        print(f"\n📈 DRIVER PAYROLL DATA ANALYSIS:")
        
        cur.execute("""
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT employee_id) as unique_employees,
                MIN(pay_date) as earliest_payroll,
                MAX(pay_date) as latest_payroll,
                SUM(CASE WHEN gross_pay > 0 THEN gross_pay ELSE 0 END) as total_gross_pay,
                SUM(CASE WHEN total_deductions < 0 THEN total_deductions ELSE 0 END) as total_deductions_amount,
                AVG(gross_pay) FILTER (WHERE gross_pay IS NOT NULL) as avg_gross_pay
            FROM driver_payroll
        """)
        
        payroll_stats = cur.fetchone()
        
        for key, value in payroll_stats.items():
            if 'pay' in key and value and 'avg' in key:
                print(f"   {key.replace('_', ' ').title()}: ${value:.2f}")
            elif 'pay' in key and value and 'total' in key:
                print(f"   {key.replace('_', ' ').title()}: ${value:,.2f}")
            elif 'deductions' in key and value:
                print(f"   {key.replace('_', ' ').title()}: ${abs(value):,.2f}")
            else:
                print(f"   {key.replace('_', ' ').title()}: {value}")
        
        # 3. Check if driver_payroll has detailed payroll_item breakdown
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'driver_payroll' AND table_schema = 'public'
            AND column_name = 'payroll_item'
        """)
        
        has_payroll_item = cur.fetchone()
        
        if has_payroll_item:
            print(f"\n💼 PAYROLL ITEMS BREAKDOWN:")
            
            cur.execute("""
                SELECT 
                    payroll_item,
                    COUNT(*) as occurrence_count,
                    SUM(amount) as total_amount,
                    AVG(amount) as avg_amount,
                    COUNT(DISTINCT employee_id) as unique_employees
                FROM driver_payroll
                WHERE payroll_item IS NOT NULL
                GROUP BY payroll_item
                ORDER BY SUM(amount) DESC
                LIMIT 20
            """)
            
            payroll_items = cur.fetchall()
            
            for item in payroll_items:
                print(f"   {item['payroll_item']}: {item['occurrence_count']:,} entries")
                print(f"      Total: ${item['total_amount']:,.2f}, Avg: ${item['avg_amount']:.2f}")
                print(f"      Employees: {item['unique_employees']}")
        else:
            print(f"\n💼 PAYROLL STRUCTURE:")
            print(f"   driver_payroll uses summary format (no detailed payroll_item breakdown)")
            print(f"   Detailed payroll items likely in staging_driver_pay table")
        
        # 4. Employee Payroll Summary
        print(f"\n👥 EMPLOYEE PAYROLL SUMMARY:")
        
        cur.execute("""
            SELECT 
                e.full_name,
                e.employee_number,
                COUNT(dp.id) as payroll_entries,
                SUM(CASE WHEN dp.gross_pay > 0 THEN dp.gross_pay ELSE 0 END) as total_earnings,
                SUM(CASE WHEN dp.total_deductions < 0 THEN dp.total_deductions ELSE 0 END) as total_deductions,
                SUM(dp.net_pay) as net_pay
            FROM employees e
            LEFT JOIN driver_payroll dp ON e.employee_id = dp.employee_id
            WHERE dp.id IS NOT NULL
            GROUP BY e.employee_id, e.full_name, e.employee_number
            ORDER BY SUM(dp.net_pay) DESC
            LIMIT 15
        """)
        
        employee_summaries = cur.fetchall()
        
        for emp in employee_summaries:
            print(f"   {emp['full_name']} (#{emp['employee_number']}):")
            print(f"      Entries: {emp['payroll_entries']:,}")
            print(f"      Earnings: ${emp['total_earnings']:,.2f}")
            print(f"      Deductions: ${emp['total_deductions']:,.2f}")
            print(f"      Net Pay: ${emp['net_pay']:,.2f}")
        
        # 5. Staging Tables Analysis
        print(f"\n📥 STAGING TABLES ANALYSIS:")
        
        # First check what columns exist in staging_driver_pay
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'staging_driver_pay' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        
        staging_columns = [row['column_name'] for row in cur.fetchall()]
        print(f"   staging_driver_pay columns: {', '.join(staging_columns[:10])}...")
        
        cur.execute("""
            SELECT 
                COUNT(*) as total_staging_records,
                COUNT(DISTINCT driver_name) as unique_drivers,
                COUNT(DISTINCT file_id) as unique_files,
                SUM(CASE WHEN gross_amount > 0 THEN gross_amount ELSE 0 END) as total_gross_amount,
                SUM(CASE WHEN expense_amount > 0 THEN expense_amount ELSE 0 END) as total_expense_amount
            FROM staging_driver_pay
        """)
        
        staging_stats = cur.fetchone()
        print(f"   Total Staging Records: {staging_stats['total_staging_records']:,}")
        print(f"   Unique Drivers: {staging_stats['unique_drivers']}")
        print(f"   Unique Files: {staging_stats['unique_files']}")
        print(f"   Total Gross Amount: ${staging_stats['total_gross_amount']:,.2f}")
        print(f"   Total Expense Amount: ${staging_stats['total_expense_amount']:,.2f}")
        
        # Get recent staging entries
        cur.execute("""
            SELECT file_id, driver_name, txn_date, pay_type, gross_amount, expense_amount
            FROM staging_driver_pay 
            ORDER BY id DESC 
            LIMIT 5
        """)
        
        print(f"\n   Recent Staging Entries:")
        for row in cur.fetchall():
            gross_amount = row['gross_amount'] or 0
            driver_name = row['driver_name'] or 'Unknown'
            txn_date = row['txn_date'] or 'No Date'
            pay_type = row['pay_type'] or 'Unknown'
            print(f"   - File {row['file_id']}: {driver_name} | {txn_date} | {pay_type} | ${gross_amount:,.2f}")
        
        # 6. Payroll Files Analysis
        print(f"\n📁 PAYROLL FILES ANALYSIS:")
        
        # Check if staging files table exists
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE '%staging%driver%pay%file%'
        """)
        
        staging_file_tables = [row['table_name'] for row in cur.fetchall()]
        print(f"   Staging file tables found: {staging_file_tables}")
        
        # Get file statistics from staging_driver_pay
        cur.execute("""
            SELECT 
                file_id,
                COUNT(*) as record_count,
                COUNT(DISTINCT driver_name) as unique_drivers,
                SUM(gross_amount) as total_gross,
                MIN(txn_date) as earliest_date,
                MAX(txn_date) as latest_date
            FROM staging_driver_pay
            GROUP BY file_id
            ORDER BY record_count DESC
            LIMIT 10
        """)
        
        file_stats = cur.fetchall()
        
        print(f"\n   Top Staging Files by Record Count:")
        for file_info in file_stats:
            total_gross = file_info['total_gross'] or 0
            print(f"   File {file_info['file_id']}: {file_info['record_count']:,} records, {file_info['unique_drivers']} drivers, ${total_gross:,.2f} total")
        
        # 7. Charter vs Payroll Comparison
        print(f"\n🔗 CHARTER VS PAYROLL COMPARISON:")
        
        cur.execute("""
            SELECT 
                COUNT(DISTINCT c.assigned_driver_id) as drivers_in_charters,
                COUNT(DISTINCT dp.employee_id) as employees_in_payroll
            FROM charters c
            FULL OUTER JOIN driver_payroll dp ON c.assigned_driver_id = dp.employee_id
        """)
        
        comparison = cur.fetchone()
        
        for key, value in comparison.items():
            print(f"   {key.replace('_', ' ').title()}: {value}")
        
        # 8. Monthly Payroll Trends
        print(f"\n📅 MONTHLY PAYROLL TRENDS (Last 12 months):")
        
        cur.execute("""
            SELECT 
                DATE_TRUNC('month', pay_date) as month,
                COUNT(*) as payroll_entries,
                COUNT(DISTINCT employee_id) as unique_employees,
                SUM(CASE WHEN gross_pay > 0 THEN gross_pay ELSE 0 END) as total_earnings,
                SUM(CASE WHEN total_deductions < 0 THEN total_deductions ELSE 0 END) as total_deductions
            FROM driver_payroll
            WHERE pay_date >= NOW() - INTERVAL '12 months'
            GROUP BY DATE_TRUNC('month', pay_date)
            ORDER BY month DESC
        """)
        
        monthly_trends = cur.fetchall()
        
        for month in monthly_trends:
            print(f"   {month['month'].strftime('%Y-%m')}: {month['payroll_entries']:,} entries")
            print(f"      Employees: {month['unique_employees']}")
            print(f"      Earnings: ${month['total_earnings']:,.2f}")
            print(f"      Deductions: ${month['total_deductions']:,.2f}")
        
        # 9. Pay Entry Tables Analysis
        print(f"\n💳 PAY ENTRY TABLES ANALYSIS:")
        
        pay_entry_tables = ['chauffeur_pay_entries', 'driver_pay_entries', 'employee_pay_entries']
        
        for table in pay_entry_tables:
            try:
                cur.execute(f"SELECT COUNT(*) as count FROM {table}")
                count = cur.fetchone()['count']
                print(f"   {table}: {count:,} records")
                
                if count > 0:
                    # Check what columns exist
                    cur.execute(f"""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = '{table}' AND table_schema = 'public'
                        ORDER BY ordinal_position
                    """)
                    columns = [row['column_name'] for row in cur.fetchall()]
                    
                    # Build query based on available columns
                    amount_col = 'amount' if 'amount' in columns else ('gross_amount' if 'gross_amount' in columns else 'pay_amount')
                    date_col = 'created_at' if 'created_at' in columns else ('pay_date' if 'pay_date' in columns else 'date')
                    
                    if amount_col in columns and date_col in columns:
                        cur.execute(f"""
                            SELECT 
                                MIN({date_col}) as earliest,
                                MAX({date_col}) as latest,
                                SUM({amount_col}) as total_amount
                            FROM {table}
                        """)
                        stats = cur.fetchone()
                        print(f"      Date range: {stats['earliest']} to {stats['latest']}")
                        print(f"      Total amount: ${stats['total_amount']:,.2f}")
                    else:
                        print(f"      Available columns: {', '.join(columns[:5])}...")
            except Exception as e:
                print(f"   {table}: Error - {e}")
        
        # 10. Summary
        print(f"\n🎯 PAYROLL SYSTEM SUMMARY:")
        print(f"   Main Payroll Records: {payroll_stats['total_records']:,}")
        print(f"   Staging Records: {staging_stats['total_staging_records']:,}")
        print(f"   Unique Employees in Payroll: {payroll_stats['unique_employees']}")
        print(f"   Date Range: {payroll_stats['earliest_payroll']} to {payroll_stats['latest_payroll']}")
        print(f"   Total Gross Pay: ${payroll_stats['total_gross_pay']:,.2f}")
        print(f"   Average Pay per Entry: ${payroll_stats['avg_gross_pay']:,.2f}")
        print(f"   Employee ID Linkage: {comparison['employees_in_payroll']} payroll employees vs {comparison['drivers_in_charters']} charter drivers")
        
    except Exception as e:
        print(f"[FAIL] Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()